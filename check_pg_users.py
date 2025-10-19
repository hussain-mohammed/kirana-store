#!/usr/bin/env python3
"""
Check PostgreSQL database users and permissions
"""

import os
import psycopg2
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

POSTGRES_URL = os.getenv("DATABASE_URL")

def check_users():
    """Check users in PostgreSQL database"""

    try:
        # Connect to PostgreSQL
        conn = psycopg2.connect(POSTGRES_URL)
        cursor = conn.cursor()

        print("✅ Connected to PostgreSQL")

        # Check users table and permissions
        cursor.execute("""
        SELECT
            id, username, email,
            sales, purchase, create_product, delete_product,
            sales_ledger, purchase_ledger, stock_ledger,
            profit_loss, opening_stock, user_management,
            is_active
        FROM users
        """)

        users = cursor.fetchall()
        print(f"\nUsers found: {len(users)}")

        for user in users:
            print(f"\n👤 User ID: {user[0]}")
            print(f"   Username: {user[1]}")
            print(f"   Email: {user[2]}")
            print(f"   Active: {bool(user[-1])}")
            print("   🗝️ Permissions:")
            print(f"     Sales: {bool(user[3])}")
            print(f"     Purchase: {bool(user[4])}")
            print(f"     Create Product: {bool(user[5])}")
            print(f"     Delete Product: {bool(user[6])}")
            print(f"     Sales Ledger: {bool(user[7])}")
            print(f"     Purchase Ledger: {bool(user[8])}")
            print(f"     Stock Ledger: {bool(user[9])}")
            print(f"     Profit & Loss: {bool(user[10])}")
            print(f"     Opening Stock: {bool(user[11])}")
            print(f"     User Management: {bool(user[12])}")

            # Check if user is the one we're looking for
            if user[1] == 'raza123':  # Verify create_product permission
                if not bool(user[5]):
                    print("   ⚠️  WARNING: This user cannot create products!")
                    return False
                else:
                    print("   ✅ This user can create products!")

        conn.close()
        return True

    except Exception as e:
        print(f"❌ Error: {e}")
        return False

if __name__ == "__main__":
    success = check_users()
    if not success:
        print("\n❌ User 'raza123' does not have create_product permission!")
    else:
        print("\n✅ All users have proper permissions for their roles.")
