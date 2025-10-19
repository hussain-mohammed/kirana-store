#!/usr/bin/env python3
"""
Migrate data from SQLite to PostgreSQL
"""

import os
import sqlite3
import psycopg2
from psycopg2.extras import execute_values
from dotenv import load_dotenv
import bcrypt
from datetime import datetime, timezone, timedelta
import json

# Load environment variables
load_dotenv()

# Database URLs
SQLITE_DB = "kirana_store.db"
POSTGRES_URL = os.getenv("DATABASE_URL")

print("🚀 Starting migration from SQLite to PostgreSQL")
print(f"📱 Source: {SQLITE_DB}")
print(f"📡 Target: {POSTGRES_URL}")

def get_sqlite_data():
    """Extract all data from SQLite database"""
    conn = sqlite3.connect(SQLITE_DB)
    conn.row_factory = sqlite3.Row  # Enable column access by name
    cursor = conn.cursor()

    data = {
        'users': [],
        'products': [],
        'sales': [],
        'purchases': []
    }

    # Get users
    cursor.execute("SELECT * FROM users")
    users = cursor.fetchall()
    for user in users:
        user_dict = dict(user)
        data['users'].append(user_dict)

    # Get products
    cursor.execute("SELECT * FROM products")
    products = cursor.fetchall()
    for product in products:
        product_dict = dict(product)
        data['products'].append(product_dict)

    # Get sales
    cursor.execute("SELECT * FROM sales")
    sales = cursor.fetchall()
    for sale in sales:
        sale_dict = dict(sale)
        data['sales'].append(sale_dict)

    # Get purchases
    cursor.execute("SELECT * FROM purchases")
    purchases = cursor.fetchall()
    for purchase in purchases:
        purchase_dict = dict(purchase)
        data['purchases'].append(purchase_dict)

    conn.close()

    print(f"📊 SQLite data extracted:")
    print(f"   - Users: {len(data['users'])}")
    print(f"   - Products: {len(data['products'])}")
    print(f"   - Sales: {len(data['sales'])}")
    print(f"   - Purchases: {len(data['purchases'])}")

    return data

def migrate_to_postgres(data):
    """Migrate data to PostgreSQL"""
    try:
        # Connect to PostgreSQL
        conn = psycopg2.connect(POSTGRES_URL)
        cursor = conn.cursor()

        print("✅ Connected to PostgreSQL")

        # Clear existing data (optional - be careful!)
        print("🧹 Clearing existing data...")
        cursor.execute("DELETE FROM sales")
        cursor.execute("DELETE FROM purchases")
        cursor.execute("DELETE FROM products")
        cursor.execute("DELETE FROM users")
        print("✅ Existing data cleared")

        # Set IST timezone
        IST = timezone(timedelta(hours=5, minutes=30))

        # Migrate users
        print("👤 Migrating users...")
        for user in data['users']:
            # Check if password is already hashed (starts with $2b$)
            password_hash = user['password_hash']
            if not password_hash.startswith('$2b$'):
                # Plain text password, hash it
                hashed = bcrypt.hashpw(password_hash.encode('utf-8'), bcrypt.gensalt())
                password_hash = hashed.decode('utf-8')

            cursor.execute("""
                INSERT INTO users (
                    id, username, email, password_hash, sales, purchase, create_product,
                    delete_product, sales_ledger, purchase_ledger, stock_ledger,
                    profit_loss, opening_stock, user_management, is_active,
                    created_at, last_login
                ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
            """, (
                user['id'], user['username'], user['email'], password_hash,
                bool(user['sales']), bool(user['purchase']), bool(user['create_product']),
                bool(user['delete_product']), bool(user['sales_ledger']), bool(user['purchase_ledger']),
                bool(user['stock_ledger']), bool(user['profit_loss']), bool(user['opening_stock']),
                bool(user['user_management']), bool(user['is_active']),
                user['created_at'], user['last_login']
            ))

        # Migrate products
        print("📦 Migrating products...")
        for product in data['products']:
            cursor.execute("""
                INSERT INTO products (
                    id, name, purchase_price, selling_price, unit_type, stock, created_at
                ) VALUES (%s, %s, %s, %s, %s, %s, %s)
            """, (
                product['id'], product['name'], product['purchase_price'],
                product['selling_price'], product['unit_type'], product['stock'],
                product['created_at']
            ))

        # Migrate sales
        print("💰 Migrating sales...")
        for sale in data['sales']:
            cursor.execute("""
                INSERT INTO sales (
                    id, product_id, quantity, total_amount, sale_date, created_by
                ) VALUES (%s, %s, %s, %s, %s, %s)
            """, (
                sale['id'], sale['product_id'], sale['quantity'],
                sale['total_amount'], sale['sale_date'], sale['created_by']
            ))

        # Migrate purchases
        print("🛒 Migrating purchases...")
        for purchase in data['purchases']:
            cursor.execute("""
                INSERT INTO purchases (
                    id, product_id, quantity, total_cost, purchase_date, created_by
                ) VALUES (%s, %s, %s, %s, %s, %s)
            """, (
                purchase['id'], purchase['product_id'], purchase['quantity'],
                purchase['total_cost'], purchase['purchase_date'], purchase['created_by']
            ))

        # Commit changes
        conn.commit()

        # Get final counts
        cursor.execute("SELECT COUNT(*) FROM users")
        users_count = cursor.fetchone()[0]

        cursor.execute("SELECT COUNT(*) FROM products")
        products_count = cursor.fetchone()[0]

        cursor.execute("SELECT COUNT(*) FROM sales")
        sales_count = cursor.fetchone()[0]

        cursor.execute("SELECT COUNT(*) FROM purchases")
        purchases_count = cursor.fetchone()[0]

        print(f"✅ Migration completed!")
        print(f"   - Users: {users_count}")
        print(f"   - Products: {products_count}")
        print(f"   - Sales: {sales_count}")
        print(f"   - Purchases: {purchases_count}")

        # Specifically show that rehan user was migrated
        cursor.execute("SELECT id, username, email FROM users WHERE username = 'rehan'")
        rehan_user = cursor.fetchone()
        if rehan_user:
            print(f"✅ User 'rehan' successfully migrated with ID: {rehan_user[0]}")

    except Exception as e:
        print(f"❌ Migration failed: {e}")
        conn.rollback()
        raise
    finally:
        cursor.close()
        conn.close()

if __name__ == "__main__":
    try:
        # Get SQLite data
        sqlite_data = get_sqlite_data()

        # Migrate to PostgreSQL
        if POSTGRES_URL:
            migrate_to_postgres(sqlite_data)
            print("\n🎉 Migration successful! Your user 'rehan' should now be visible in Railway PostgreSQL.")
        else:
            print("❌ PostgreSQL DATABASE_URL not found!")
            exit(1)

    except Exception as e:
        print(f"❌ Migration script failed: {e}")
        exit(1)
