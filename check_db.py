import sqlite3
import os

def check_users():
    db_path = 'kirana_store.db'
    if not os.path.exists(db_path):
        print(f"Database file {db_path} not found!")
        return

    try:
        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()

        # Check users table
        cursor.execute("SELECT name FROM sqlite_master WHERE type='table';")
        tables = cursor.fetchall()
        print(f"Tables in database: {[t[0] for t in tables]}")

        if 'users' in [t[0] for t in tables]:
            cursor.execute("SELECT id, username, email, is_active FROM users")
            users = cursor.fetchall()
            print(f"Users found: {len(users)}")
            for user in users:
                print(f"  - ID: {user[0]}, Username: {user[1]}, Email: {user[2]}, Active: {user[3]}")
        else:
            print("Users table not found!")

        conn.close()
    except Exception as e:
        print(f"Error: {e}")

if __name__ == "__main__":
    check_users()
