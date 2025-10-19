import sqlite3

conn = sqlite3.connect('kirana_store.db')
cursor = conn.cursor()

# Get all tables
cursor.execute("SELECT name FROM sqlite_master WHERE type='table'")
tables = cursor.fetchall()

print("Tables in database:")
for table in tables:
    table_name = table[0]
    print(f"\n📋 Table: {table_name}")

    # Get column info
    cursor.execute(f"PRAGMA table_info({table_name})")
    columns = cursor.fetchall()
    column_names = [col[1] for col in columns]
    print(f"Columns: {column_names}")

    # Get row count
    cursor.execute(f"SELECT COUNT(*) FROM {table_name}")
    row_count = cursor.fetchone()[0]
    print(f"Rows: {row_count}")

    # Get sample data if any
    if row_count > 0:
        cursor.execute(f"SELECT * FROM {table_name} LIMIT 5")
        sample_data = cursor.fetchall()
        print(f"Sample data: {sample_data}")

conn.close()
