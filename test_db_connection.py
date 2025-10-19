#!/usr/bin/env python3
"""
Test database connection with current configuration
"""

import os
from sqlalchemy import create_engine, text
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

DATABASE_URL = os.getenv('DATABASE_URL')
USE_SQLITE = os.getenv('USE_SQLITE', 'true').lower() == 'true'

if USE_SQLITE:
    DATABASE_URL = 'sqlite:///./kirana_store.db'

print(f'Using database: {"SQLite" if USE_SQLITE else "PostgreSQL"}')
print(f'DATABASE_URL: {DATABASE_URL}')

try:
    engine = create_engine(DATABASE_URL, connect_args={'check_same_thread': False} if USE_SQLITE else {})

    with engine.connect() as conn:
        # Test each table
        result = conn.execute(text('SELECT COUNT(*) as user_count FROM users'))
        user_count = result.fetchone()[0]

        result = conn.execute(text('SELECT COUNT(*) as product_count FROM products'))
        product_count = result.fetchone()[0]

        result = conn.execute(text('SELECT COUNT(*) as sales_count FROM sales'))
        sales_count = result.fetchone()[0]

        result = conn.execute(text('SELECT COUNT(*) as purchases_count FROM purchases'))
        purchases_count = result.fetchone()[0]

    print('✅ Database checks successful!')
    print(f'Users: {user_count}')
    print(f'Products: {product_count}')
    print(f'Sales: {sales_count}')
    print(f'Purchases: {purchases_count}')

except Exception as e:
    print(f'❌ Database connection failed: {e}')
