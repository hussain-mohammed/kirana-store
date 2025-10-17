#!/usr/bin/env python3
"""
Database setup script - Create tables in PostgreSQL according to main.py models
"""

import os
from dotenv import load_dotenv
from datetime import datetime, timezone, timedelta
from sqlalchemy import create_engine, Column, Integer, String, Float, DateTime, Boolean, ForeignKey, Enum
from sqlalchemy.orm import declarative_base, sessionmaker
from sqlalchemy.exc import SQLAlchemyError
import enum

# Need bcrypt for password hashing
import bcrypt
from sqlalchemy import text

from api.main import Product, Sale, Purchase, User

# Load environment variables
load_dotenv()

DATABASE_URL = os.getenv("DATABASE_URL")

print("🚀 Setting up PostgreSQL database according to main.py models")
print(f"📡 Database: {DATABASE_URL}")

# Create engine
engine = create_engine(DATABASE_URL)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

Base = declarative_base()

def create_tables():
    """Create all tables defined in main.py models"""
    try:
        print("📝 Creating tables in PostgreSQL...")

        # Create tables
        Base.metadata.create_all(bind=engine)

        print("✅ Tables created successfully!")

        # Create default admin user
        db = SessionLocal()
        try:
            # Check if admin user already exists
            existing_admin = db.query(User).filter(User.username == "raza123").first()
            if not existing_admin:
                print("👤 Creating default admin user...")
                default_password = "admin123"
                hashed_password = bcrypt.hashpw(default_password.encode('utf-8'), bcrypt.gensalt())

                default_admin = User(
                    username="raza123",
                    email="admin@kirana.store",
                    password_hash=hashed_password.decode('utf-8'),
                    # Give all permissions to default admin
                    sales=True,
                    purchase=True,
                    create_product=True,
                    delete_product=True,
                    sales_ledger=True,
                    purchase_ledger=True,
                    stock_ledger=True,
                    profit_loss=True,
                    opening_stock=True,
                    user_management=True,
                    is_active=True
                )
                db.add(default_admin)
                db.commit()
                print(f"✅ Default admin user created: username=raza123, password={default_password}")
            else:
                print("ℹ️  Admin user already exists")

        except Exception as e:
            print(f"⚠️  Error creating admin user: {e}")
        finally:
            db.close()

        return True

    except Exception as e:
        print(f"❌ Failed to create tables: {e}")
        return False

def migrate_sample_data():
    """Add sample data if database is empty"""
    db = SessionLocal()
    try:
        # Check if products exist
        product_count = db.query(Product).count()
        if product_count == 0:
            print("🛍️ Adding sample products...")
            IST = timezone(timedelta(hours=5, minutes=30))
            sample_products = [
                Product(name="Apple", purchase_price=80.00, selling_price=100.00, unit_type="kgs", stock=50),
                Product(name="Banana", purchase_price=40.00, selling_price=50.00, unit_type="kgs", stock=30),
                Product(name="Orange", purchase_price=60.00, selling_price=80.00, unit_type="kgs", stock=25),
                Product(name="Milk", purchase_price=50.00, selling_price=65.00, unit_type="ltr", stock=20),
                Product(name="Bread", purchase_price=30.00, selling_price=40.00, unit_type="pcs", stock=15),
                Product(name="Eggs", purchase_price=70.00, selling_price=90.00, unit_type="pcs", stock=40),
                Product(name="Rice", purchase_price=100.00, selling_price=120.00, unit_type="kgs", stock=60),
                Product(name="Sugar", purchase_price=45.00, selling_price=55.00, unit_type="kgs", stock=35),
            ]
            db.add_all(sample_products)
            db.commit()
            print(f"✅ Added {len(sample_products)} sample products")
        else:
            print(f"ℹ️  Database already contains {product_count} products")

    except Exception as e:
        print(f"❌ Error adding sample data: {e}")
    finally:
        db.close()

def test_connection():
    """Test database connection"""
    try:
        db = SessionLocal()
        db.execute(text("SELECT 1"))
        db.close()
        print("✅ Database connection test successful")
        return True
    except Exception as e:
        print(f"❌ Database connection test failed: {e}")
        return False

if __name__ == "__main__":
    print("="*60)
    print("🔧 DATABASE SETUP FOR VERBEL DEPLOYMENT")
    print("="*60)

    # Test connection
    if test_connection():
        # Create tables
        if create_tables():
            # Add sample data
            migrate_sample_data()
            print("\n🎉 Setup completed successfully!")
            print("\n📋 Database now ready with:")
            print("   - Users table with default admin (raza123/admin123)")
            print("   - Products, Sales, Purchases tables")
            print("   - Sample products for testing")
            print("\n🚀 Ready for Vercel deployment!")
        else:
            print("❌ Setup failed!")
            exit(1)
    else:
        print("❌ Database connection failed!")
        exit(1)
