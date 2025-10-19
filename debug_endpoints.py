#!/usr/bin/env python3
"""
Debug script to test Kirana Store API endpoints
Tests both login and ledger endpoints to diagnose the issue
"""

import requests
import json
import sys

# Configuration
BASE_URL = "https://kirana-store-backend-production.up.railway.app"
# BASE_URL = "http://localhost:8000"  # For local testing

def main():
    session = requests.Session()

    print("🧪 Testing Kirana Store API Endpoints")
    print("=" * 50)

    try:
        # Step 1: Test basic health
        print("\n1. Testing health endpoint...")
        response = session.get(f"{BASE_URL}/health")
        if response.status_code == 200:
            print("✅ Health endpoint working")
            print(f"   Response: {response.json()}")
        else:
            print(f"❌ Health endpoint failed: {response.status_code}")
            return

        # Step 2: Login as default admin
        print("\n2. Testing login as default admin...")
        login_data = {
            "username": "raza123",
            "password": "admin123"
        }
        response = session.post(f"{BASE_URL}/auth/login", json=login_data)

        if response.status_code == 200:
            login_result = response.json()
            access_token = login_result.get("access_token")
            if access_token:
                print("✅ Login successful")
                # Set Authorization header for future requests
                session.headers.update({"Authorization": f"Bearer {access_token}"})
                print(f"   User: {login_result.get('user', {}).get('username')}")
                permissions = login_result.get('user', {}).get('permissions', [])
                print(f"   Permissions: {permissions}")

                # Check specific permissions
                required_perms = ['sales_ledger', 'purchase_ledger', 'profit_loss', 'opening_stock']
                for perm in required_perms:
                    if perm in permissions:
                        print(f"   ✅ Has {perm} permission")
                    else:
                        print(f"   ❌ Missing {perm} permission")
            else:
                print("❌ Login failed - no access token received")
                return
        else:
            print(f"❌ Login failed: {response.status_code}")
            print(f"   Response: {response.text}")
            return

        # Step 3: Test ledger endpoints
        endpoints_to_test = [
            ("Sales Ledger", "/ledger/sales"),
            ("Purchase Ledger", "/ledger/purchases"),
            ("Ledger Summary", "/ledger/summary"),
            ("Stock Snapshot", "/products/stock-snapshot"),
            ("Opening Stock", "/opening-stock-register"),
            ("Profit Loss Data", "/profit-loss-data")
        ]

        for name, endpoint in endpoints_to_test:
            print(f"\n3. Testing {name} endpoint ({endpoint})...")
            response = session.get(f"{BASE_URL}{endpoint}")

            if response.status_code == 200:
                data = response.json()
                print("✅ Endpoint working")

                # Analyze response
                if isinstance(data, list):
                    print(f"   Returned {len(data)} records")
                    if len(data) > 0:
                        if 'sales_ledger' in name.lower() or 'purchase_ledger' in name.lower():
                            sample = data[0]
                            keys = list(sample.keys())[:5]  # First 5 keys
                            print(f"   Sample record fields: {keys}")
                        elif 'stock' in name.lower():
                            print("   Stock data available")
                elif isinstance(data, dict):
                    print(f"   Returned dictionary with keys: {list(data.keys())}")
                    if 'summary' in data:
                        summary = data['summary']
                        print(f"   Summary - Products: {summary.get('total_products')}, Purchases: {summary.get('total_purchases')}, Sales: {summary.get('total_sales')}")

            elif response.status_code == 403:
                print("❌ Access denied - permission required")
                print(f"   Response: {response.text}")
            else:
                print(f"❌ Endpoint failed: {response.status_code}")
                print(f"   Response: {response.text}")

        print("\n" + "=" * 50)
        print("✅ All tests completed")

    except requests.RequestException as e:
        print(f"❌ Network error: {e}")
        print("\nSuggestions:")
        print("- Check if the server is running")
        print("- Verify the BASE_URL is correct")
        print("- Check network connectivity")
    except Exception as e:
        print(f"❌ Unexpected error: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    main()
