import sqlite3

conn = sqlite3.connect('kirana_store.db')
cursor = conn.cursor()
cursor.execute('SELECT id, username, email, password_hash FROM users')
print('Users:')
for row in cursor.fetchall():
    print(f"ID: {row[0]}")
    print(f"Username: {row[1]}")
    print(f"Email: {row[2]}")
    print(f"Password Hash: {repr(row[3])}")
conn.close()
