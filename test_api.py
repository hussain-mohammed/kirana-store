#!/usr/bin/env python3
"""
Test the API health endpoint
"""

import requests
import time

# Wait a bit for server to start
print("Waiting for server to start...")
time.sleep(2)

try:
    response = requests.get("http://localhost:8000/health", timeout=10)
    if response.status_code == 200:
        data = response.json()
        print("✅ Health endpoint responded successfully!")
        print(f"Status: {data.get('status')}")
        print(f"Database: {data.get('database')}")
        print(f"Timestamp: {data.get('timestamp')}")

        # Test products endpoint too
        products_response = requests.get("http://localhost:8000/products", timeout=10)
        if products_response.status_code == 200:
            products = products_response.json()
            print(f"✅ Products endpoint working! Found {len(products)} products")
        else:
            print(f"❌ Products endpoint failed: {products_response.status_code}")

    else:
        print(f"❌ Health endpoint failed: {response.status_code}")
        print(response.text)

except requests.RequestException as e:
    print(f"❌ Request failed: {e}")
    print("Server might not be running. Please start the server manually with: python main.py")
