"""
test_api.py

Run this AFTER starting the server in a separate terminal window with:
    uvicorn app.main:app --reload

This script calls the API the same way the dashboard eventually will,
so we can confirm the backend works before building any UI on top of it.
"""

import requests

BASE_URL = "http://127.0.0.1:8000"
PR_NUMBER = 2  # the low-risk retry helper PR — good first test

print(f"=== Triaging PR #{PR_NUMBER} via the API ===")
response = requests.post(f"{BASE_URL}/api/triage/{PR_NUMBER}")
response.raise_for_status()
print(response.json())

print("\n=== Checking the pending review queue ===")
response = requests.get(f"{BASE_URL}/api/suggestions/pending")
response.raise_for_status()
for item in response.json():
    print(item)
