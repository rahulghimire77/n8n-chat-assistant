import os

import requests
import truststore

user_message = "Can you tell me about black holes in 3 to 4 lines?"

request_message = {"message": user_message}

url = "https://rgh.app.n8n.cloud/webhook/daea1d3e-d6c7-4738-a05c-9d4b0c18a2a2"
verify_ssl = os.getenv("VERIFY_SSL", "true").lower() != "false"

truststore.inject_into_ssl()

session = requests.Session()
session.trust_env = False

try:
    response = session.post(
        url,
        json=request_message,
        timeout=30,
        verify=verify_ssl,
    )
    print("Status:", response.status_code)
    response.raise_for_status()
    if response.headers.get("content-type", "").startswith("application/json"):
        try:
            print(response.json())
        except ValueError:
            print("Response body was not valid JSON.")
            print(repr(response.text))
    else:
        print(repr(response.text))
except requests.exceptions.SSLError as exc:
    print("SSL verification failed:", exc)
    print("For local debugging only, run with: $env:VERIFY_SSL='false'; py .\\vs_studio\\test_webhook.py")
except requests.exceptions.RequestException as exc:
    print("Request failed:", exc)
