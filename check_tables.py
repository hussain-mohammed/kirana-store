import sqlite3

# Connect to SQLite database
conn = sqlite3.connect('kirana.db')
cursor = conn.cursor()

# Get all tables
cursor.execute("SELECT name FROM sqlite_master WHERE type='table'")
tables = cursor.fetchall()

print("Tables in SQLite database:")
for table in tables:
    table_name = table[0]
    print(f"\n📋 Table: {table_name}")

    # Get table schema
    cursor.execute(f"PRAGMA table_info({table_name})")
    columns = cursor.fetchall()
    print("Columns:", [col[1] for col in columns])

    # Get row count
    cursor.execute(f"SELECT COUNT(*) FROM {table_name}")
    count = cursor.fetchone()[0]
    print(f"Rows: {count}")

    # Show sample data
    if count > 0:
        cursor.execute(f"SELECT * FROM {table_name} LIMIT 3")
        sample = cursor.fetchall()
        print("Sample data:", sample)

conn.close()
