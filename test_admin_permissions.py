#!/usr/bin/env python3
"""
Test admin permissions for user raza123
"""

import requests
import json

BASE_URL = "http://localhost:8000"

def test_login():
    """Test login with raza123"""
    login_url = f"{BASE_URL}/auth/login"

    user_data = {
        "username": "raza123",
        "password": "123456"
    }

    print("🔐 Testing login for user 'raza123'...")

    try:
        response = requests.post(login_url, json=user_data)
        print(f"Status Code: {response.status_code}")

        if response.status_code == 200:
            response_data = response.json()
            access_token = response_data.get("access_token")
            user = response_data.get("user")

            print("✅ Login successful!")
            print(f"👤 User: {user.get('username')} ({user.get('email')})")
            print(f"🔑 Permissions: {user.get('permissions', [])}")

            return access_token
        else:
            print("❌ Login failed")
            print(response.text)
            return None

    except Exception as e:
        print(f"❌ Login request failed: {e}")
        return None

def test_create_product(token):
    """Test creating a product with admin permissions"""
    create_url = f"{BASE_URL}/products/"

    headers = {
        "Authorization": f"Bearer {token}",
        "Content-Type": "application/json"
    }

    product_data = {
        "name": "Test Product Admin",
        "purchase_price": 50.00,
        "selling_price": 70.00,
        "unit_type": "kgs",
        "stock": 25
    }

    print("🔧 Testing product creation...")

    try:
        response = requests.post(create_url, json=product_data, headers=headers)
        print(f"Status Code: {response.status_code}")

        if response.status_code == 201:
            response_data = response.json()
            print("✅ Product created successfully!")
            print(f"📦 Product: {response_data.get('name')} (ID: {response_data.get('id')})")
            return True
        else:
            print("❌ Product creation failed")
            print(f"Response: {response.text}")
            return False

    except Exception as e:
        print(f"❌ Product creation request failed: {e}")
        return False

def main():
    print("🧪 Testing admin permissions for user 'raza123'\n")

    # Test login
    token = test_login()

    if not token:
        print("❌ Cannot proceed without login token")
        return

    print()

    # Test product creation
    success = test_create_product(token)

    print()
    if success:
        print("🎉 All tests passed! User 'raza123' has admin permissions and can create products.")
    else:
        print("❌ Tests failed! Please check user permissions.")

if __name__ == "__main__":
    main()
