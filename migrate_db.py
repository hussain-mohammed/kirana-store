#!/usr/bin/env python3
"""
Database migration script to move data from SQLite to PostgreSQL
"""

import os
from dotenv import load_dotenv
from sqlalchemy import create_engine, MetaData
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker

# Load environment variables
load_dotenv()

# Database URLs
OLD_DATABASE_URL = "sqlite:///kirana.db"  # SQLite database
NEW_DATABASE_URL = os.getenv("DATABASE_URL")  # Neon Postgres

print("🚀 Starting database migration from SQLite to PostgreSQL")
print(f"📡 Old DB: {OLD_DATABASE_URL}")
print(f"📡 New DB: {NEW_DATABASE_URL}")

# Create engines
old_engine = create_engine(OLD_DATABASE_URL)
new_engine = create_engine(NEW_DATABASE_URL)

# Create metadata
metadata = MetaData()

try:
    # Reflect existing tables from old database
    metadata.reflect(bind=old_engine)

    tables_to_migrate = ['users', 'products', 'sales', 'purchases']

    # Create tables in new database
    print("📝 Creating tables in PostgreSQL...")
    metadata.create_all(bind=new_engine, tables=[metadata.tables[t] for t in tables_to_migrate if t in metadata.tables])

    # Migrate data for each table
    for table_name in tables_to_migrate:
        if table_name in metadata.tables:
            print(f"🔄 Migrating table: {table_name}")

            # Get data from old database
            table = metadata.tables[table_name]
            with old_engine.connect() as old_conn:
                result = old_conn.execute(table.select())
                rows = result.fetchall()

            print(f"  📊 Found {len(rows)} rows in {table_name}")

            if rows:
                # Insert data into new database
                with new_engine.connect() as new_conn:
                    new_conn.execute(table.insert(), [dict(row._mapping) for row in rows])
                    new_conn.commit()

                print(f"  ✅ Migrated {len(rows)} rows to {table_name}")

    print("🎉 Migration completed successfully!")

except Exception as e:
    print(f"❌ Migration failed: {e}")
    raise
