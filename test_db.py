import os
from dotenv import load_dotenv
from sqlalchemy import create_engine

load_dotenv()

DATABASE_URL = os.getenv("DATABASE_URL")
print(f"Testing connection to Neon Postgres: {DATABASE_URL}")

try:
    engine = create_engine(DATABASE_URL)
    conn = engine.connect()
    print("✅ Neon Postgres connection successful")
    conn.close()
except Exception as e:
    print(f"❌ Connection failed: {e}")
