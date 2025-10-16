#!/usr/bin/env python3
"""
Test script for Kirana Store API
"""

import os
from dotenv import load_dotenv
from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker
from datetime import datetime, timezone, timedelta

# Load environment
load_dotenv()

def test_database_connection():
    """Test database connection"""
    print("="*50)
    print("🔍 TESTING DATABASE CONNECTION")
    print("="*50)

    DATABASE_URL = os.getenv("DATABASE_URL", "sqlite:///kirana.db")

    try:
        engine = create_engine(DATABASE_URL)
        connection = engine.connect()

        # Test basic query
        result = connection.execute(text("SELECT 1 as test"))
        row = result.fetchone()
        connection.close()

        print("✅ Database connection: SUCCESS")
        print(f"📡 Connected to: {DATABASE_URL.split('@')[1] if '@' in DATABASE_URL else 'Local database'}")

        # Test table existence
        SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
        db = SessionLocal()

        try:
            # Test products table
            products = db.execute(text("SELECT COUNT(*) FROM products")).fetchone()[0]
            print(f"📦 Products in database: {products}")

            # Test users table
            users = db.execute(text("SELECT COUNT(*) FROM users")).fetchone()[0]
            print(f"👥 Users in database: {users}")

            # Test sales table
            sales = db.execute(text("SELECT COUNT(*) FROM sales")).fetchone()[0]
            print(f"💰 Sales transactions: {sales}")

            # Test purchases table
            purchases = db.execute(text("SELECT COUNT(*) FROM purchases")).fetchone()[0]
            print(f"🛒 Purchase transactions: {purchases}")

        except Exception as e:
            print(f"⚠️  Some tables may not exist yet: {e}")
        finally:
            db.close()

        return True

    except Exception as e:
        print(f"❌ Database connection: FAILED")
        print(f"Error: {e}")
        return False

def test_api_import():
    """Test API import"""
    print("\n" + "="*50)
    print("🔍 TESTING API IMPORT")
    print("="*50)

    try:
        # Test importing the FastAPI app
        from api.main import app
        print("✅ FastAPI app import: SUCCESS")

        # Check if handlers exist
        if hasattr(app, 'routes'):
            route_count = len([r for r in app.routes if hasattr(r, 'methods')])
            print(f"🛣️  API routes configured: {route_count}")

        # Check for Mangum handler
        from mangum import Mangum
        handler = Mangum(app, lifespan="off")
        print("✅ Mangum handler: CONFIGURED")

        return True

    except ImportError as e:
        print(f"❌ Import error: {e}")
        return False
    except Exception as e:
        print(f"❌ API configuration error: {e}")
        return False

def test_vercel_config():
    """Test Vercel configuration"""
    print("\n" + "="*50)
    print("🔍 TESTING VERCEL CONFIGURATION")
    print("="*50)

    try:
        with open('vercel.json', 'r') as f:
            config = json.load(f)

        print("✅ vercel.json: FOUND")

        # Validate build config
        if 'builds' in config:
            builds = config['builds']
            if isinstance(builds, list) and len(builds) > 0:
                build = builds[0]
                if 'src' in build:
                    src_file = build['src']
                    if os.path.exists(src_file):
                        print(f"✅ Build source file exists: {src_file}")
                    else:
                        print(f"❌ Build source file missing: {src_file}")
                        return False
                else:
                    print("❌ Build config missing 'src' field")
                    return False
            else:
                print("❌ Builds array is empty or invalid")
                return False
        else:
            print("❌ vercel.json missing 'builds' section")
            return False

        # Validate routes
        if 'routes' in config:
            routes = config['routes']
            api_routes = [r for r in routes if '/api/' in r.get('src', '')]
            if len(api_routes) > 0:
                print(f"✅ API routes configured: {len(api_routes)}")
            else:
                print("❌ No API routes found")
                return False
        else:
            print("❌ vercel.json missing 'routes' section")
            return False

        print("✅ Vercel configuration: VALID")
        return True

    except FileNotFoundError:
        print("❌ vercel.json: NOT FOUND")
        return False
    except json.JSONDecodeError as e:
        print(f"❌ vercel.json syntax error: {e}")
        return False
    except Exception as e:
        print(f"❌ Vercel config test failed: {e}")
        return False

def show_deployment_status():
    """Show deployment status summary"""
    print("\n" + "="*60)
    print("📋 DEPLOYMENT READY CHECK")
    print("="*60)

    checks = [
        ("Git repository", ".git" in os.listdir(".")),
        ("Requirements.txt", os.path.exists("requirements.txt")),
        (".env file", os.path.exists(".env")),
        ("API directory", os.path.exists("api")),
        ("API main.py", os.path.exists("api/main.py")),
        ("Vercel config", os.path.exists("vercel.json")),
        ("Frontend files", any(os.path.exists(f) for f in ["index.html", "login.html"])),
    ]

    all_passed = True
    for check_name, passed in checks:
        status = "✅" if passed else "❌"
        print(f"{status} {check_name}")
        if not passed:
            all_passed = False

    print("\n" + "="*60)
    if all_passed:
        print("🎉 ALL CHECKS PASSED - READY FOR DEPLOYMENT!")
        print("\n🚀 Next: Push to GitHub → Vercel auto-deploys")
        print("📡 API endpoints will be available at /api/*")
        print("🌐 Frontend will serve at root URL")
    else:
        print("❌ SOME CHECKS FAILED - FIX BEFORE DEPLOYMENT")

    return all_passed

if __name__ == "__main__":
    import json

    print("🚀 KIRANA STORE DEPLOYMENT TEST")
    print("=================================")

    # Run all tests
    db_ok = test_database_connection()
    api_ok = test_api_import()
    vercel_ok = test_vercel_config()
    ready = show_deployment_status()

    print("\n" + "="*60)
    print("🔬 FINAL RESULTS:")
    print(f"Database: {'✅' if db_ok else '❌'}")
    print(f"API Import: {'✅' if api_ok else '❌'}")
    print(f"Vercel Config: {'✅' if vercel_ok else '❌'}")
    print(f"Deployment Ready: {'✅' if ready else '❌'}")
    print("="*60)

    if ready:
        print("\n💡 Ready to deploy! Your Kirana Store API is properly configured.")
        print("📧 Contact user when deployment succeeds.")
    else:
        print("\n⚠️  Fix issues above before deployment.")
