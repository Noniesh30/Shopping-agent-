import requests
import json
import os
import pandas as pd

url = "http://127.0.0.1:8000"

response = requests.post(
    f"{url}/send",
    json={
        "data": {
            "user_prompt": "Show me black shoes with white shirt",
        }
    }
)
print("====================================================")
print("Send Data:")
print(response.json())

response = requests.get("http://127.0.0.1:8000/receive")

print("====================================================")

print("Recieved Data:")
response.raise_for_status()
received_data = response.json()

os.makedirs("Memory", exist_ok=True)
with open("Memory/received_data.json", "w", encoding="utf-8") as file:
    json.dump(received_data['data'], file, indent=4, ensure_ascii=False)

print("Data saved to received_data.json")