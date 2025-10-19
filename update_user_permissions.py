#!/usr/bin/env python3
"""
Update user permissions in PostgreSQL database
"""

import os
import psycopg2
from dotenv import load_dotenv
import bcrypt

# Load environment variables
load_dotenv()

POSTGRES_URL = os.getenv("DATABASE_URL")

def update_user_permissions():
    """Update user permissions for raza123"""

    try:
        # Connect to PostgreSQL
        conn = psycopg2.connect(POSTGRES_URL)
        cursor = conn.cursor()

        print("✅ Connected to PostgreSQL")
        print("🔄 Updating user 'raza123' with admin permissions...")

        # Hash the password "123456"
        password_hash = bcrypt.hashpw("123456".encode('utf-8'), bcrypt.gensalt()).decode('utf-8')

        # Update the user with admin permissions and correct password
        cursor.execute('''
        UPDATE users SET
            sales = true,
            purchase = true,
            create_product = true,
            delete_product = true,
            sales_ledger = true,
            purchase_ledger = true,
            stock_ledger = true,
            profit_loss = true,
            opening_stock = true,
            user_management = true,
            password_hash = %s
        WHERE username = %s
        ''', (password_hash, 'raza123'))

        conn.commit()

        # Check if the update was successful
        if cursor.rowcount > 0:
            print("✅ User 'raza123' updated successfully!")

            # Verify the permissions
            cursor.execute("""
            SELECT username, sales, purchase, create_product, delete_product, user_management
            FROM users WHERE username = %s
            """, ('raza123',))

            user = cursor.fetchone()
            if user:
                print(f"✅ Verified permissions for {user[0]}: sales={user[1]}, purchase={user[2]}, create_product={user[3]}, delete_product={user[4]}, user_management={user[5]}")
            else:
                print("❌ Could not verify user after update")
        else:
            print("❌ No user found with username 'raza123'")

        conn.close()
        print("✅ Database update completed!")

    except Exception as e:
        print(f"❌ Update failed: {e}")
        if 'conn' in locals():
            conn.rollback()
            conn.close()
        raise

if __name__ == "__main__":
    update_user_permissions()
