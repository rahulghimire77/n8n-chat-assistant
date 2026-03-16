import json
import os
import re
from http import HTTPStatus
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Any

import requests
import truststore


HOST = os.getenv("HOST", "0.0.0.0")
PORT = int(os.getenv("PORT", "8000"))
WEBHOOK_URL = "https://rgh.app.n8n.cloud/webhook/daea1d3e-d6c7-4738-a05c-9d4b0c18a2a2"
UI_FILE = Path(__file__).with_name("chat_ui.html")


truststore.inject_into_ssl()


def normalize_text(text: str) -> str:
    lines = [re.sub(r"\s+", " ", line).strip() for line in text.splitlines()]
    cleaned = "\n".join(line for line in lines if line)
    return cleaned.strip()


def extract_text(payload: Any) -> str | None:
    if isinstance(payload, str):
        text = normalize_text(payload)
        return text or None

    if isinstance(payload, list):
        for item in payload:
            text = extract_text(item)
            if text:
                return text
        return None

    if isinstance(payload, dict):
        preferred_keys = (
            "reply",
            "response",
            "message",
            "output",
            "text",
            "answer",
            "content",
            "result",
        )
        for key in preferred_keys:
            text = extract_text(payload.get(key))
            if text:
                return text

        for value in payload.values():
            text = extract_text(value)
            if text:
                return text

    return None


def ask_assistant(message: str) -> str:
    session = requests.Session()
    session.trust_env = False

    response = session.post(
        WEBHOOK_URL,
        json={"message": message},
        timeout=60,
    )
    response.raise_for_status()

    content_type = response.headers.get("content-type", "")
    if "application/json" in content_type:
        payload = response.json()
        text = extract_text(payload)
        if text:
            return text
        return "The webhook returned JSON, but no readable assistant message was found."

    body = response.text.strip()
    return body or "The webhook returned an empty response."


class ChatHandler(BaseHTTPRequestHandler):
    def do_GET(self) -> None:
        if self.path in ("/", "/index.html"):
            html = UI_FILE.read_text(encoding="utf-8")
            self.send_response(HTTPStatus.OK)
            self.send_header("Content-Type", "text/html; charset=utf-8")
            self.end_headers()
            self.wfile.write(html.encode("utf-8"))
            return

        self.send_error(HTTPStatus.NOT_FOUND, "Not found")

    def do_POST(self) -> None:
        if self.path != "/chat":
            self.send_error(HTTPStatus.NOT_FOUND, "Not found")
            return

        try:
            content_length = int(self.headers.get("Content-Length", "0"))
            raw_body = self.rfile.read(content_length)
            payload = json.loads(raw_body.decode("utf-8"))
            message = str(payload.get("message", "")).strip()

            if not message:
                self._send_json(HTTPStatus.BAD_REQUEST, {"error": "Message cannot be empty."})
                return

            reply = ask_assistant(message)
            self._send_json(HTTPStatus.OK, {"reply": reply})
        except requests.exceptions.HTTPError as exc:
            detail = exc.response.text.strip() if exc.response is not None else str(exc)
            self._send_json(
                HTTPStatus.BAD_GATEWAY,
                {"error": f"Webhook error: {detail or exc}"},
            )
        except requests.exceptions.RequestException as exc:
            self._send_json(
                HTTPStatus.BAD_GATEWAY,
                {"error": f"Could not reach the webhook: {exc}"},
            )
        except json.JSONDecodeError:
            self._send_json(HTTPStatus.BAD_REQUEST, {"error": "Invalid JSON payload."})
        except Exception as exc:
            self._send_json(HTTPStatus.INTERNAL_SERVER_ERROR, {"error": f"Unexpected error: {exc}"})

    def log_message(self, format: str, *args) -> None:
        return

    def _send_json(self, status: HTTPStatus, payload: dict) -> None:
        body = json.dumps(payload).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)


def main() -> None:
    server = ThreadingHTTPServer((HOST, PORT), ChatHandler)
    print(f"Chat UI running at http://{HOST}:{PORT}")
    print("Connected to the published production webhook.")
    server.serve_forever()


if __name__ == "__main__":
    main()
