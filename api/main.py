from datetime import datetime, timezone, timedelta
import os
import io
import csv
from contextlib import asynccontextmanager
from typing import List, Optional, Any, Dict
from dotenv import load_dotenv
from fastapi import FastAPI, HTTPException, Request, status, Depends, Form
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from pydantic import BaseModel, Field
from sqlalchemy import create_engine, Column, Integer, String, Float, DateTime, Boolean, text
from sqlalchemy.orm import declarative_base, sessionmaker, Session, relationship
from sqlalchemy import ForeignKey, Enum as SQLEnum
import enum
import jwt
import bcrypt
from fastapi.responses import JSONResponse
from fastapi.middleware.cors import CORSMiddleware
from twilio.twiml.messaging_response import MessagingResponse
from fastapi import HTTPException
from sqlalchemy.exc import SQLAlchemyError

# JWT Secret Key
SECRET_KEY_JWT = os.getenv("SECRET_KEY", "your-secret-key-change-this-in-production")

# Load environment variables from .env file for local development
load_dotenv()

DATABASE_URL = os.getenv("DATABASE_URL")
if not DATABASE_URL:
        print("❌ ERROR: DATABASE_URL not set in environment variables!")
        print("Please set your DATABASE_URL environment variable to connect to PostgreSQL")
        print("Example: postgresql://username:password@hostname:port/database_name")
        print("For local development, create a .env file with your DATABASE_URL")
        # Don't crash the app, but it won't work without database
else:
        print(f"📡 Connecting to database: {DATABASE_URL.split('@')[1] if '@' in DATABASE_URL else 'Local database'}")

# Initialize the HTTPBearer instance
security = HTTPBearer()

# Create a SQLAlchemy engine
engine = create_engine(DATABASE_URL)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

# Base class for declarative models
Base = declarative_base()

# --- Database Models ---
IST = timezone(timedelta(hours=5, minutes=30))

class UserRole(enum.Enum):
    ADMIN = "admin"
    MANAGER = "manager"
    EMPLOYEE = "employee"

class Permission(enum.Enum):
    SALES = "sales"
    PURCHASE = "purchase"
    CREATE_PRODUCT = "create_product"
    DELETE_PRODUCT = "delete_product"
    SALES_LEDGER = "sales_ledger"
    PURCHASE_LEDGER = "purchase_ledger"
    STOCK_LEDGER = "stock_ledger"
    PROFIT_LOSS = "profit_loss"
    OPENING_STOCK = "opening_stock"
    USER_MANAGEMENT = "user_management"

# Permissions for each role
ROLE_PERMISSIONS = {
    UserRole.ADMIN.value: [
        Permission.SALES,
        Permission.PURCHASE,
        Permission.CREATE_PRODUCT,
        Permission.DELETE_PRODUCT,
        Permission.SALES_LEDGER,
        Permission.PURCHASE_LEDGER,
        Permission.STOCK_LEDGER,
        Permission.PROFIT_LOSS,
        Permission.OPENING_STOCK,
        Permission.USER_MANAGEMENT,
    ],
    UserRole.MANAGER.value: [
        Permission.SALES,
        Permission.PURCHASE,
        Permission.SALES_LEDGER,
        Permission.PURCHASE_LEDGER,
        Permission.STOCK_LEDGER,
        Permission.OPENING_STOCK,
    ],
    UserRole.EMPLOYEE.value: [
        Permission.SALES,
        Permission.PURCHASE,
    ],
}

class User(Base):
    """User authentication and role management."""
    __tablename__ = "users"

    id = Column(Integer, primary_key=True, index=True)
    username = Column(String, unique=True, index=True, nullable=False)
    email = Column(String, unique=True, index=True, nullable=False)
    password_hash = Column(String, nullable=False)
    # Individual permissions instead of roles
    sales = Column(Boolean, default=True)
    purchase = Column(Boolean, default=True)
    create_product = Column(Boolean, default=True)
    delete_product = Column(Boolean, default=True)
    sales_ledger = Column(Boolean, default=True)
    purchase_ledger = Column(Boolean, default=True)
    stock_ledger = Column(Boolean, default=True)
    profit_loss = Column(Boolean, default=True)
    opening_stock = Column(Boolean, default=True)
    user_management = Column(Boolean, default=True)
    is_active = Column(Boolean, default=True)
    created_at = Column(DateTime, default=lambda: datetime.now(IST))
    last_login = Column(DateTime, nullable=True)

    # Sales relationship
    user_sales = relationship("Sale", back_populates="user", lazy=True)
    # Purchases relationship
    user_purchases = relationship("Purchase", back_populates="user", lazy=True)

class Product(Base):
    """Represents a product in the store."""
    __tablename__ = "products"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String, unique=True, index=True, nullable=False)
    purchase_price = Column(Float, nullable=False)  # Cost price when buying from supplier
    selling_price = Column(Float, nullable=False)   # Selling price to customers
    unit_type = Column(String, nullable=False)      # Unit type: kgs, ltr, or pcs
    stock = Column(Integer, default=0)
    created_at = Column(DateTime, default=lambda: datetime.now(IST))

class Sale(Base):
    """Records a single sale transaction."""
    __tablename__ = "sales"

    id = Column(Integer, primary_key=True, index=True)
    product_id = Column(Integer, ForeignKey("products.id"))
    quantity = Column(Integer, nullable=False)
    total_amount = Column(Float, nullable=False)
    sale_date = Column(DateTime, default=lambda: datetime.now(IST))
    created_by = Column(Integer, ForeignKey("users.id"), nullable=True)
    product = relationship("Product")
    user = relationship("User", lazy=True)

class Purchase(Base):
    """Records a purchase of stock from a supplier."""
    __tablename__ = "purchases"

    id = Column(Integer, primary_key=True, index=True)
    product_id = Column(Integer, ForeignKey("products.id"))
    quantity = Column(Integer, nullable=False)
    total_cost = Column(Float, nullable=False)
    purchase_date = Column(DateTime, default=lambda: datetime.now(IST))
    created_by = Column(Integer, ForeignKey("users.id"), nullable=True)
    product = relationship("Product")
    user = relationship("User", lazy=True)

# --- Pydantic Models for API Requests/Responses ---
class ProductBase(BaseModel):
    name: str
    purchase_price: float = Field(..., gt=0, description="Purchase price must be a positive number")
    selling_price: float = Field(..., gt=0, description="Selling price must be a positive number")
    unit_type: str = Field(..., description="Unit type: kgs, ltr, or pcs")

class ProductCreate(ProductBase):
    stock: int = Field(0, ge=0, description="Initial stock level")

class ProductUpdate(BaseModel):
    name: Optional[str] = None
    purchase_price: Optional[float] = None
    selling_price: Optional[float] = None
    unit_type: Optional[str] = None
    stock: Optional[int] = None

class ProductResponse(ProductCreate):
    id: int
    created_at: datetime

class SaleCreate(BaseModel):
    product_id: int
    quantity: int = Field(..., gt=0, description="Quantity must be positive")

class SaleResponse(BaseModel):
    id: int
    product_id: int
    quantity: int
    total_amount: float
    sale_date: datetime

class PurchaseCreate(BaseModel):
    product_id: int
    quantity: int = Field(..., gt=0, description="Quantity must be positive")
    unit_cost: float = Field(..., gt=0, description="Cost per unit must be positive")

class PurchaseResponse(BaseModel):
    id: int
    product_id: int
    quantity: int
    total_cost: float
    purchase_date: datetime

class OrderItem(BaseModel):
    product_name: str
    quantity: int

class WhatsAppOrderRequest(BaseModel):
    customer_name: str
    phone_number: str
    items: List[OrderItem]

    class Config:
        schema_extra = {
            "example": {
                "customer_name": "John Doe",
                "phone_number": "+919876543210",
                "items": [
                    {"product_name": "Milk", "quantity": 2},
                    {"product_name": "Bread", "quantity": 1}
                ]
            }
        }

class PurchaseLedgerEntry(BaseModel):
    purchase_id: int
    date: datetime
    product_id: int
    product_name: str
    quantity: int
    unit_cost: float
    total_cost: float
    supplier_info: Optional[str] = None

class SalesLedgerEntry(BaseModel):
    sale_id: int
    date: datetime
    product_id: int
    product_name: str
    quantity: int
    unit_price: float
    total_amount: float
    customer_info: Optional[str] = None

class ProductStockHistory(BaseModel):
    date: datetime
    transaction_type: str  # "PURCHASE", "SALE", "OPENING"
    reference: str
    quantity: int
    stock_after_transaction: int
    details: str

class ProductStockLedger(BaseModel):
    product_id: int
    product_name: str
    current_stock: int
    opening_stock: int
    total_purchases: int
    total_sales: int
    history: List[ProductStockHistory]

class ProductStockSnapshot(BaseModel):
    product_id: int
    product_name: str
    price: float
    stock: int
    stock_value: float
    unit_type: str
    last_updated: datetime

# --- Pydantic Models for Authentication ---
class LoginRequest(BaseModel):
    username: str
    password: str

class UserResponse(BaseModel):
    id: int
    username: str
    email: str
    # Optionally include role for legacy users
    role: Optional[str] = None
    is_active: bool
    # Include permissions for new system
    permissions: Optional[List[str]] = None

class UserCreateRequest(BaseModel):
    username: str
    password: str
    email: str
    sales: bool = False
    purchase: bool = False
    create_product: bool = False
    delete_product: bool = False
    sales_ledger: bool = False
    purchase_ledger: bool = False
    stock_ledger: bool = False
    profit_loss: bool = False
    opening_stock: bool = False
    user_management: bool = False

class LoginResponse(BaseModel):
    access_token: str
    token_type: str
    user: UserResponse

# Authentication functions
def authenticate_user(db: Session, username: str, password: str):
    user = db.query(User).filter(User.username == username).first()
    if not user:
        print(f"⚠️ User '{username}' not found")
        return None
    if not bcrypt.checkpw(password.encode('utf-8'), user.password_hash.encode('utf-8')):
        print(f"⚠️ Invalid password for user '{username}'")
        return None
    print(f"✅ Authentication successful for user '{username}'")
    return user

def create_access_token(data: dict):
    to_encode = data.copy()
    expire = datetime.utcnow() + timedelta(hours=24)  # Token expires in 24 hours
    to_encode.update({"exp": expire})
    encoded_jwt = jwt.encode(to_encode, SECRET_KEY_JWT, algorithm="HS256")
    return encoded_jwt

def verify_token(credentials: HTTPAuthorizationCredentials = Depends(security)):
    try:
        payload = jwt.decode(credentials.credentials, SECRET_KEY_JWT, algorithms=["HS256"])
        username: str = payload.get("sub")
        if username is None:
            raise HTTPException(status_code=401, detail="Invalid authentication credentials")
        return username
    except jwt.ExpiredSignatureError:
        raise HTTPException(status_code=401, detail="Token has expired")
    except jwt.PyJWTError:
        raise HTTPException(status_code=401, detail="Invalid authentication credentials")


# Dependency to get a database session
def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

# Lifespan event to create the database tables on startup
@asynccontextmanager
async def lifespan(app: FastAPI):
    try:
        # Create database tables
        Base.metadata.create_all(bind=engine)
        print("Database tables created.")

        # Seed with sample data if no products exist
        db = SessionLocal()
        try:
            # Test database connection first
            db.execute(text("SELECT 1"))

            # Check if the new columns exist by trying to query them
            try:
                # Try to access the new columns to see if they exist
                db.query(Product.purchase_price, Product.selling_price, Product.unit_type).first()
                print("✅ New database schema detected")

                product_count = db.query(Product).count()
                if product_count == 0:
                    print("No products found in database. You can create products through the web interface.")
                    print("To add sample products, use the 'Create Product' page in the application.")
                else:
                    print(f"Database already contains {product_count} products.")

            except Exception as column_error:
                print(f"⚠️ Schema mismatch detected: {column_error}")
                print("🔄 Attempting to update database schema...")

                # For PostgreSQL/Render, use a safer approach
                try:
                    # First, try to add the missing column without dropping tables
                    try:
                        # Check if created_at column exists
                        result = db.execute(text("SELECT created_at FROM products LIMIT 1"))
                        print("✅ created_at column already exists")
                    except Exception:
                        print("📝 Adding created_at column to products table...")
                        # Add the missing column
                        db.execute(text("ALTER TABLE products ADD COLUMN created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP"))
                        print("✅ created_at column added successfully")

                    # Update existing records with current timestamp if they don't have created_at
                    try:
                        db.execute(text("UPDATE products SET created_at = CURRENT_TIMESTAMP WHERE created_at IS NULL"))
                        db.commit()
                        print("✅ Existing records updated with creation timestamps")
                    except Exception as update_error:
                        print(f"⚠️ Could not update existing records: {update_error}")
                        # This is not critical, so we'll continue

                    print("✅ Database schema updated successfully")

                    # Check if we need sample data
                    product_count = db.query(Product).count()
                    if product_count == 0:
                        # Create default admin user if no users exist
                        user_count = db.query(User).count()
                        if user_count == 0:
                            default_password = "admin123"
                            hashed_password = bcrypt.hashpw(default_password.encode('utf-8'), bcrypt.gensalt())

                            default_admin = User(
                                username="raza123",
                                email="admin@kirana.store",
                                password_hash=hashed_password.decode('utf-8'),
                                # New permission system - give all permissions to default admin
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
                            print("⚠️  PLEASE CHANGE THE DEFAULT PASSWORD AFTER FIRST LOGIN!")

                        print("Seeding database with sample products...")
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
                        print("✅ Sample products added to database.")
                    else:
                        print(f"Database already contains {product_count} products.")

                except Exception as update_error:
                    print(f"❌ Failed to update schema: {update_error}")
                    print("🔄 Falling back to table recreation method...")

                    try:
                        # As a last resort, try the drop/create method
                        Base.metadata.drop_all(bind=engine)
                        Base.metadata.create_all(bind=engine)
                        print("✅ Database schema recreated successfully")

                        # Now add sample data
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
                        print("✅ Sample products added to database.")

                    except Exception as final_error:
                        print(f"❌ Failed to recreate schema: {final_error}")
                        print("Please check your DATABASE_URL and ensure the database is accessible")

        except Exception as e:
            print(f"Database initialization error: {e}")
            # Don't let database errors crash the entire app
            pass
        finally:
            db.close()

    except Exception as e:
        print(f"❌ Critical database error: {e}")
        # Don't let database errors crash the entire app
        pass

    yield

# --- FastAPI App Initialization ---
app = FastAPI(
    title="Kirana Store Management API",
    description="A backend for managing a local Kirana store's products, sales, and purchases, including an online order simulation.",
    lifespan=lifespan
)

# === FIXED CORS CONFIGURATION ===
origins = [
    "http://localhost:8000",
    "http://127.0.0.1:8000",
    "http://localhost:5500",
    "http://127.0.0.1:5500",
    "https://nonnitric-ably-candra.ngrok-free.dev",
    "http://nonnitric-ably-candra.ngrok-free.dev",
    "https://*.ngrok-free.dev",
    "http://*.ngrok-free.dev",
      "https://kirana-store-seven.vercel.app",  # Add your Vercel frontend
    "https://*.vercel.app",
    "https://kirana-store-backend.onrender.com",
    "https://kirana-store-maoc.onrender.com",
    "https://kirana-store-docker.onrender.com",
    "*"
]

app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,
    allow_credentials=True,
    allow_methods=["GET", "POST", "PUT", "DELETE", "OPTIONS", "HEAD"],
    allow_headers=["*"],
    expose_headers=["*"],
    max_age=600,
)

# === CORS OPTIONS HANDLERS ===
@app.options("/{path:path}")
async def options_handler(path: str):
    return JSONResponse(
        content={},
        headers={
            "Access-Control-Allow-Origin": "*",
            "Access-Control-Allow-Methods": "GET, POST, PUT, DELETE, OPTIONS",
            "Access-Control-Allow-Headers": "*",
            "Access-Control-Max-Age": "600"
        }
    )
