import os
os.environ["USE_SQLITE"] = "false"  # Force PostgreSQL usage

import requests
import json

# Test the registration endpoint
url = "http://localhost:8000/auth/register"

user_data = {
    "username": "rehan",
    "password": "self123"
}

print("Testing user registration...")
try:
    response = requests.post(url, json=user_data)
    print(f"Status Code: {response.status_code}")
    print(f"Response: {response.text}")

    if response.status_code == 201:
        print("✅ User created successfully!")
    else:
        print("❌ User creation failed")

except Exception as e:
    print(f"❌ Request failed: {e}")
    print("Make sure the server is running with: python main.py")

# Test login
login_url = "http://localhost:8000/auth/login"
print("\nTesting login...")
try:
    response = requests.post(login_url, json=user_data)
    print(f"Status Code: {response.status_code}")
    print(f"Response: {response.text}")

    if response.status_code == 200:
        print("✅ Login successful!")
    else:
        print("❌ Login failed")

except Exception as e:
    print(f"❌ Login request failed: {e}")
