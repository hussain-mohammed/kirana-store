#!/usr/bin/env python3
"""
Script to add sample data to the Kirana Store database
This will create sample products, sales, and purchases to populate the ledger pages
"""

import requests
import json
import random
from datetime import datetime, timedelta

# Configuration
BASE_URL = "https://kirana-store-backend-production.up.railway.app"

# Authenticate as admin
def login():
    print("🔐 Logging in as admin...")
    response = requests.post(f"{BASE_URL}/auth/login", json={
        "username": "raza123",
        "password": "123456"
    })

    if response.status_code != 200:
        print(f"❌ Login failed: {response.text}")
        return None

    token = response.json()["access_token"]
    print("✅ Login successful")
    return token

def make_request(method, endpoint, token, data=None):
    headers = {"Authorization": f"Bearer {token}"}
    url = f"{BASE_URL}{endpoint}"

    if method == "GET":
        response = requests.get(url, headers=headers)
    elif method == "POST":
        response = requests.post(url, headers=headers, json=data)
    else:
        print(f"❌ Unsupported method: {method}")
        return None

    return response

def add_sample_products(token):
    print("\n📦 Adding sample products...")

    # Check existing products first
    response = make_request("GET", "/products", token)
    if response.status_code == 200:
        existing_products = response.json()
        if len(existing_products) > 0:
            print(f"✅ Already have {len(existing_products)} products")
            return existing_products

    # Add sample products
    sample_products = [
        {"name": "Rice", "purchase_price": 95.0, "selling_price": 110.0, "unit_type": "kgs", "stock": 100},
        {"name": "Sugar", "purchase_price": 40.0, "selling_price": 50.0, "unit_type": "kgs", "stock": 75},
        {"name": "Milk", "purchase_price": 45.0, "selling_price": 58.0, "unit_type": "ltr", "stock": 50},
        {"name": "Bread", "purchase_price": 25.0, "selling_price": 35.0, "unit_type": "pcs", "stock": 30},
        {"name": "Eggs", "purchase_price": 65.0, "selling_price": 80.0, "unit_type": "pcs", "stock": 60},
        {"name": "Apples", "purchase_price": 80.0, "selling_price": 100.0, "unit_type": "kgs", "stock": 40},
        {"name": "Bananas", "purchase_price": 35.0, "selling_price": 45.0, "unit_type": "kgs", "stock": 55},
        {"name": "Tea", "purchase_price": 180.0, "selling_price": 220.0, "unit_type": "kgs", "stock": 20}
    ]

    products = []
    for product in sample_products:
        response = make_request("POST", "/products/", token, product)
        if response.status_code == 201:
            new_product = response.json()
            products.append(new_product)
            print(f"✅ Added product: {new_product['name']}")
        else:
            print(f"❌ Failed to add {product['name']}: {response.text}")

    return products

def add_sample_purchases(token, products):
    print("\n🛒 Adding sample purchases...")

    purchases = []
    for product in products:
        # Create 2-3 purchase records per product over the last 30 days
        num_purchases = random.randint(2, 4)

        for i in range(num_purchases):
            # Random quantity and cost variation
            base_quantity = 20 if product["unit_type"] == "kgs" else (10 if product["unit_type"] == "ltr" else 15)
            quantity = random.randint(base_quantity//2, base_quantity*2)

            # Unit cost slightly less than current purchase price
            unit_cost_variation = random.uniform(0.95, 1.05)
            unit_cost = product["purchase_price"] * unit_cost_variation

            purchase_data = {
                "product_id": product["id"],
                "quantity": quantity,
                "unit_cost": round(unit_cost, 2)
            }

            response = make_request("POST", "/purchases/", token, purchase_data)
            if response.status_code == 201:
                purchase = response.json()
                purchases.append(purchase)
                print(f"✅ Purchase for {product['name']}: {quantity} units at ₹{unit_cost:.2f}")
            else:
                print(f"❌ Purchase failed for {product['name']}: {response.text}")

    return purchases

def add_sample_sales(token, products):
    print("\n💰 Adding sample sales...")

    sales = []
    for product in products:
        # Create 1-2 sale records per product over the last 30 days
        num_sales = random.randint(1, 3)

        for i in range(num_sales):
            # Random sale date within last 30 days
            sale_date = datetime.now() - timedelta(days=random.randint(1, 30))

            # Random quantity based on unit type
            base_quantity = 5 if product["unit_type"] == "kgs" else (3 if product["unit_type"] == "ltr" else 8)
            quantity = random.randint(1, base_quantity)

            sale_data = {
                "product_id": product["id"],
                "quantity": quantity
            }

            response = make_request("POST", "/sales/", token, sale_data)
            if response.status_code == 201:
                sale = response.json()
                sales.append(sale)
                print(f"✅ Sale for {product['name']}: {quantity} units at ₹{product['selling_price']:.2f}")
            else:
                print(f"❌ Sale failed for {product['name']}: {response.text}")

            # Note: We'll let the auto-stock adjustment happen, even if it goes negative briefly

    return sales

def check_ledgers(token):
    print("\n📊 Checking ledger data...")

    endpoints = [
        ("/ledger/summary", "Ledger Summary"),
        ("/ledger/sales", "Sales Ledger"),
        ("/ledger/purchases", "Purchase Ledger"),
        ("/products/stock-snapshot", "Stock Snapshot"),
        ("/opening-stock-register", "Opening Stock Register")
    ]

    for endpoint, name in endpoints:
        response = make_request("GET", endpoint, token)
        if response.status_code == 200:
            data = response.json()
            if isinstance(data, list):
                print(f"✅ {name}: {len(data)} records")
            elif isinstance(data, dict) and "summary" in data:
                summary = data["summary"]
                print(f"✅ {name}: {summary.get('total_sales')} sales, {summary.get('total_purchases')} purchases")
            else:
                print(f"✅ {name}: {type(data)} data")
        else:
            print(f"❌ {name} failed: {response.status_code}")

def main():
    print("🏪 Kirana Store Sample Data Generator")
    print("=" * 50)

    # Login
    token = login()
    if not token:
        return

    # Add sample data
    products = add_sample_products(token)
    purchases = add_sample_purchases(token, products)
    sales = add_sample_sales(token, products)

    print(f"✅ Added {len(products)} products, {len(purchases)} purchases, {len(sales)} sales")

    # Check results
    check_ledgers(token)

    print("\n" + "=" * 50)
    print("✅ Sample data populated!")
    print("\n📝 Instructions:")
    print("1. Login to your Kirana Store application")
    print("2. Navigate to the Ledger pages:")
    print("   - Sales Ledger")
    print("   - Purchase Ledger")
    print("   - Profit & Loss")
    print("   - Opening Stock Register")
    print("3. You should now see transaction data")

if __name__ == "__main__":
    main()
