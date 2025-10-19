#!/usr/bin/env python3
"""
Test API endpoints for product creation with proper authentication
"""

import requests
import json

# Server URL
BASE_URL = "http://localhost:8000"

def test_product_creation():
    """Test creating a product with proper authentication"""

    # Step 1: Login to get authentication token
    print("🔐 Logging in...")
    login_data = {
        "username": "raza123",
        "password": "123456"
    }

    login_response = requests.post(f"{BASE_URL}/auth/login", json=login_data)

    if login_response.status_code != 200:
        print(f"❌ Login failed: {login_response.status_code}")
        print(login_response.text)
        return

    login_result = login_response.json()
    access_token = login_result.get("access_token")

    if not access_token:
        print("❌ No access token received")
        return

    print(f"✅ Login successful! Token: {access_token[:20]}...")

    # Step 2: Prepare authorization header
    headers = {
        "Authorization": f"Bearer {access_token}",
        "Content-Type": "application/json"
    }

    # Step 3: Create a test product
    product_data = {
        "name": "Test Product",
        "purchase_price": 50.00,
        "selling_price": 75.00,
        "unit_type": "pcs",
        "stock": 10
    }

    print("📝 Creating product...")
    create_response = requests.post(
        f"{BASE_URL}/products/",
        json=product_data,
        headers=headers
    )

    print(f"📊 Create response status: {create_response.status_code}")

    if create_response.status_code == 201:  # 201 Created
        result = create_response.json()
        print("✅ Product created successfully!")
        print(json.dumps(result, indent=2))
    elif create_response.status_code == 403:
        print("❌ Forbidden - Permission denied")
        print(create_response.text)
    elif create_response.status_code == 401:
        print("❌ Unauthorized - Authentication failed")
        print(create_response.text)
    else:
        print(f"❌ Unexpected error: {create_response.status_code}")
        print(create_response.text)

if __name__ == "__main__":
    test_product_creation()
