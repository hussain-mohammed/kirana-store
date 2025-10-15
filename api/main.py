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
        print(f"📊 Connecting to database: {DATABASE_URL.split('@')[1] if '@' in DATABASE_URL else 'Local database'}")

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
    """Authenticate user using ORM with backwards compatibility."""
    from datetime import datetime, timezone, timedelta
    IST = timezone(timedelta(hours=5, minutes=30))

    print(f"🔐 Login attempt: username='{username}', password='{password}'")

    try:
        # Query the user using ORM
        user = db.query(User).filter(User.username == username).first()
        if not user:
            print(f"❌ User '{username}' not found in database")
            return None

        print(f"👤 Found user: {user.username}, email: {user.email}, active: {user.is_active}")

        # Get the stored password
        stored_password = user.password_hash
        if not stored_password:
            print(f"⚠️ User '{username}' has no password set")
            return None

        print(f"🔑 Stored password type: {type(stored_password)}")
        print(f"🔑 Input password type: {type(password)}")

        # Try bcrypt verification first (for modern hashed passwords)
        try:
            password_match = bcrypt.checkpw(password.encode('utf-8'), stored_password.encode('utf-8'))
            if password_match:
                print(f"✅ Authenticated '{username}' with bcrypt hash")
                user.last_login = datetime.now(IST)
                db.commit()
                return user
            else:
                print(f"❌ Bcrypt verification failed for '{username}'")
        except Exception as e:
            print(f"⚠️ Bcrypt check failed, trying plain text: {str(e)}")

        # Check if it's plain text (for legacy users)
        if stored_password == password:
            print(f"✅ Authenticated '{username}' with plain text password")
            user.last_login = datetime.now(IST)
            db.commit()
            return user

        print(f"❌ Invalid password for user '{username}' - password mismatch")
        return None

    except Exception as e:
        print(f"💥 Authentication error for user '{username}': {str(e)}")
        import traceback
        traceback.print_exc()
        return None

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
                print("â New database schema detected")

                product_count = db.query(Product).count()
                if product_count == 0:
                    print("No products found in database. You can create products through the web interface.")
                    print("To add sample products, use the 'Create Product' page in the application.")
                else:
                    print(f"Database already contains {product_count} products.")

            except Exception as column_error:
                print(f"â ď¸ Schema mismatch detected: {column_error}")
                print("đ Attempting to update database schema...")

                # For PostgreSQL/Render, use a safer approach
                try:
                    # First, try to add the missing column without dropping tables
                    try:
                        # Check if created_at column exists
                        result = db.execute(text("SELECT created_at FROM products LIMIT 1"))
                        print("â created_at column already exists")
                    except Exception:
                        print("đ Adding created_at column to products table...")
                        # Add the missing column
                        db.execute(text("ALTER TABLE products ADD COLUMN created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP"))
                        print("â created_at column added successfully")

                    # Update existing records with current timestamp if they don't have created_at
                    try:
                        db.execute(text("UPDATE products SET created_at = CURRENT_TIMESTAMP WHERE created_at IS NULL"))
                        db.commit()
                        print("â Existing records updated with creation timestamps")
                    except Exception as update_error:
                        print(f"â ď¸ Could not update existing records: {update_error}")
                        # This is not critical, so we'll continue

                    print("â Database schema updated successfully")

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
                            print(f"â Default admin user created: username=raza123, password={default_password}")
                            print("â ď¸  PLEASE CHANGE THE DEFAULT PASSWORD AFTER FIRST LOGIN!")

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
                        print("â Sample products added to database.")
                    else:
                        print(f"Database already contains {product_count} products.")

                except Exception as update_error:
                    print(f"â Failed to update schema: {update_error}")
                    print("đ Falling back to table recreation method...")

                    try:
                        # As a last resort, try the drop/create method
                        Base.metadata.drop_all(bind=engine)
                        Base.metadata.create_all(bind=engine)
                        print("â Database schema recreated successfully")

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
                        print("â Sample products added to database.")

                    except Exception as final_error:
                        print(f"â Failed to recreate schema: {final_error}")
                        print("Please check your DATABASE_URL and ensure the database is accessible")

        except Exception as e:
            print(f"Database initialization error: {e}")
            # Don't let database errors crash the entire app
            pass
        finally:
            db.close()

    except Exception as e:
        print(f"â Critical database error: {e}")
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
#   T h i s   f i l e   c o n t a i n s   t h e   m i s s i n g   A P I   e n d p o i n t s   -   a p p e n d   t h i s   t o   a p i / m a i n . p y 
 
 
 
 #   - - -   A P I   E n d p o i n t   t o   s e r v e   p r o d u c t s   t o   t h e   f r o n t e n d   - - - 
 
 @ a p p . g e t ( " / p r o d u c t s " ) 
 
 a s y n c   d e f   g e t _ p r o d u c t s ( d b :   S e s s i o n   =   D e p e n d s ( g e t _ d b ) ) : 
 
         " " " R e t u r n s   t h e   l i s t   o f   r e a l   p r o d u c t s   f r o m   d a t a b a s e   f o r   t h e   f r o n t e n d   t o   d i s p l a y . " " " 
 
         t r y : 
 
                 d b _ p r o d u c t s   =   d b . q u e r y ( P r o d u c t ) . a l l ( ) 
 
                 p r i n t ( f " đ x Ś   F o u n d   { l e n ( d b _ p r o d u c t s ) }   p r o d u c t s   i n   d a t a b a s e " ) 
 
 
 
                 f r o n t e n d _ p r o d u c t s   =   [ ] 
 
 
 
                 f o r   p r o d u c t   i n   d b _ p r o d u c t s : 
 
                         f r o n t e n d _ p r o d u c t s . a p p e n d ( { 
 
                                 " i d " :   p r o d u c t . i d , 
 
                                 " n a m e " :   p r o d u c t . n a m e , 
 
                                 " p r i c e " :   f l o a t ( p r o d u c t . s e l l i n g _ p r i c e ) ,     #   U s e   s e l l i n g _ p r i c e   f o r   f r o n t e n d   d i s p l a y 
 
                                 " p u r c h a s e _ p r i c e " :   f l o a t ( p r o d u c t . p u r c h a s e _ p r i c e ) , 
 
                                 " s e l l i n g _ p r i c e " :   f l o a t ( p r o d u c t . s e l l i n g _ p r i c e ) , 
 
                                 " u n i t _ t y p e " :   s t r ( p r o d u c t . u n i t _ t y p e ) ,     #   E n s u r e   i t ' s   r e t u r n e d   a s   s t r i n g 
 
                                 " i m a g e U r l " :   " " ,     #   L e t   f r o n t e n d   g e n e r a t e   d y n a m i c   i m a g e s 
 
                                 " s t o c k " :   p r o d u c t . s t o c k 
 
                         } ) 
 
 
 
                 p r i n t ( " â S&   S u c c e s s f u l l y   f o r m a t t e d   p r o d u c t s   f o r   f r o n t e n d " ) 
 
                 r e t u r n   J S O N R e s p o n s e ( c o n t e n t = f r o n t e n d _ p r o d u c t s ,   m e d i a _ t y p e = " a p p l i c a t i o n / j s o n " ) 
 
 
 
         e x c e p t   E x c e p t i o n   a s   e : 
 
                 p r i n t ( f " â  R  E r r o r   f e t c h i n g   p r o d u c t s :   { e } " ) 
 
                 f a l l b a c k _ p r o d u c t s   =   [ 
 
                         { " i d " :   1 ,   " n a m e " :   " A p p l e " ,   " p r i c e " :   1 0 0 . 0 0 ,   " i m a g e U r l " :   " h t t p s : / / p l a c e h o l d . c o / 4 0 0 x 4 0 0 / 8 1 c 7 8 4 / f f f f f f ? t e x t = A p p l e " ,   " s t o c k " :   5 0 } , 
 
                         { " i d " :   2 ,   " n a m e " :   " B a n a n a " ,   " p r i c e " :   5 0 . 0 0 ,   " i m a g e U r l " :   " h t t p s : / / p l a c e h o l d . c o / 4 0 0 x 4 0 0 / f f f 1 7 6 / f f f f f f ? t e x t = B a n a n a " ,   " s t o c k " :   3 0 } , 
 
                 ] 
 
                 r e t u r n   J S O N R e s p o n s e ( c o n t e n t = f a l l b a c k _ p r o d u c t s ,   m e d i a _ t y p e = " a p p l i c a t i o n / j s o n " ) 
 
 
 
 #   - - -   A P I   E n d p o i n t s   f o r   P r o d u c t s   ( D B   o p e r a t i o n s )   - - - 
 
 @ a p p . p o s t ( " / p r o d u c t s / " ,   r e s p o n s e _ m o d e l = P r o d u c t R e s p o n s e ,   s t a t u s _ c o d e = s t a t u s . H T T P _ 2 0 1 _ C R E A T E D ) 
 
 d e f   c r e a t e _ p r o d u c t ( p r o d u c t :   P r o d u c t C r e a t e ,   d b :   S e s s i o n   =   D e p e n d s ( g e t _ d b ) ) : 
 
         d b _ p r o d u c t   =   P r o d u c t ( * * p r o d u c t . d i c t ( ) ) 
 
         d b . a d d ( d b _ p r o d u c t ) 
 
         d b . c o m m i t ( ) 
 
         d b . r e f r e s h ( d b _ p r o d u c t ) 
 
         r e t u r n   d b _ p r o d u c t 
 
 
 
 @ a p p . g e t ( " / p r o d u c t s / s t o c k - s n a p s h o t " ,   r e s p o n s e _ m o d e l = L i s t [ P r o d u c t S t o c k S n a p s h o t ] ) 
 
 d e f   g e t _ p r o d u c t s _ s t o c k _ s n a p s h o t ( 
 
         d a t e _ f r o m :   O p t i o n a l [ s t r ]   =   N o n e , 
 
         d a t e _ t o :   O p t i o n a l [ s t r ]   =   N o n e , 
 
         p r o d u c t _ i d :   O p t i o n a l [ i n t ]   =   N o n e , 
 
         d b :   S e s s i o n   =   D e p e n d s ( g e t _ d b ) 
 
 ) : 
 
         " " " 
 
         G e t   p r o d u c t   s t o c k   s n a p s h o t   w i t h   d a t e   f i l t e r i n g . 
 
         A l w a y s   s h o w s   p u r c h a s e   p r i c e s   f o r   i n v e n t o r y   v a l u a t i o n . 
 
         " " " 
 
         t r y : 
 
                 p r i n t ( f " đ x `  G e n e r a t i n g   s t o c k   s n a p s h o t   -   D a t e   F r o m :   { d a t e _ f r o m } ,   D a t e   T o :   { d a t e _ t o } ,   P r o d u c t   I D :   { p r o d u c t _ i d } " ) 
 
 
 
                 #   P a r s e   d a t e   f i l t e r s 
 
                 f i l t e r _ d a t e _ f r o m   =   N o n e 
 
                 f i l t e r _ d a t e _ t o   =   N o n e 
 
 
 
                 i f   d a t e _ f r o m : 
 
                         t r y : 
 
                                 t r y : 
 
                                         f i l t e r _ d a t e _ f r o m   =   d a t e t i m e . f r o m i s o f o r m a t ( d a t e _ f r o m . r e p l a c e ( ' Z ' ,   ' + 0 0 : 0 0 ' ) ) 
 
                                 e x c e p t   V a l u e E r r o r : 
 
                                         i f   l e n ( d a t e _ f r o m )   = =   1 0 : 
 
                                                 f i l t e r _ d a t e _ f r o m   =   d a t e t i m e . f r o m i s o f o r m a t ( d a t e _ f r o m ) 
 
                                         e l s e : 
 
                                                 r a i s e   V a l u e E r r o r ( f " U n s u p p o r t e d   d a t e   f o r m a t :   { d a t e _ f r o m } " ) 
 
                                 p r i n t ( f " đ x &   P a r s e d   d a t e _ f r o m :   { f i l t e r _ d a t e _ f r o m } " ) 
 
                         e x c e p t   V a l u e E r r o r   a s   e : 
 
                                 p r i n t ( f " â a  ď ¸    I n v a l i d   d a t e _ f r o m   f o r m a t :   { d a t e _ f r o m } ,   e r r o r :   { e } " ) 
 
 
 
                 i f   d a t e _ t o : 
 
                         t r y : 
 
                                 t r y : 
 
                                         f i l t e r _ d a t e _ t o   =   d a t e t i m e . f r o m i s o f o r m a t ( d a t e _ t o . r e p l a c e ( ' Z ' ,   ' + 0 0 : 0 0 ' ) ) 
 
                                 e x c e p t   V a l u e E r r o r : 
 
                                         i f   l e n ( d a t e _ t o )   = =   1 0 : 
 
                                                 f i l t e r _ d a t e _ t o   =   d a t e t i m e . f r o m i s o f o r m a t ( d a t e _ t o ) 
 
                                         e l s e : 
 
                                                 r a i s e   V a l u e E r r o r ( f " U n s u p p o r t e d   d a t e   f o r m a t :   { d a t e _ t o } " ) 
 
                                 p r i n t ( f " đ x &   P a r s e d   d a t e _ t o :   { f i l t e r _ d a t e _ t o } " ) 
 
                         e x c e p t   V a l u e E r r o r   a s   e : 
 
                                 p r i n t ( f " â a  ď ¸    I n v a l i d   d a t e _ t o   f o r m a t :   { d a t e _ t o } ,   e r r o r :   { e } " ) 
 
 
 
                 #   B a s e   q u e r y   f o r   p r o d u c t s 
 
                 q u e r y   =   d b . q u e r y ( P r o d u c t ) 
 
 
 
                 #   F i l t e r   b y   p r o d u c t   i f   s p e c i f i e d 
 
                 i f   p r o d u c t _ i d : 
 
                         q u e r y   =   q u e r y . f i l t e r ( P r o d u c t . i d   = =   p r o d u c t _ i d ) 
 
 
 
                 p r o d u c t s   =   q u e r y . a l l ( ) 
 
 
 
                 s n a p s h o t s   =   [ ] 
 
                 f o r   p r o d u c t   i n   p r o d u c t s : 
 
                         c a l c u l a t e d _ s t o c k   =   p r o d u c t . s t o c k 
 
 
 
                         i f   f i l t e r _ d a t e _ t o : 
 
                                 p u r c h a s e s   =   d b . q u e r y ( P u r c h a s e ) . f i l t e r ( 
 
                                         P u r c h a s e . p r o d u c t _ i d   = =   p r o d u c t . i d , 
 
                                         P u r c h a s e . p u r c h a s e _ d a t e   < =   f i l t e r _ d a t e _ t o 
 
                                 ) . a l l ( ) 
 
 
 
                                 s a l e s   =   d b . q u e r y ( S a l e ) . f i l t e r ( 
 
                                         S a l e . p r o d u c t _ i d   = =   p r o d u c t . i d , 
 
                                         S a l e . s a l e _ d a t e   < =   f i l t e r _ d a t e _ t o 
 
                                 ) . a l l ( ) 
 
 
 
                                 t o t a l _ p u r c h a s e s _ u p _ t o _ d a t e   =   s u m ( p . q u a n t i t y   f o r   p   i n   p u r c h a s e s ) 
 
                                 t o t a l _ s a l e s _ u p _ t o _ d a t e   =   s u m ( s . q u a n t i t y   f o r   s   i n   s a l e s ) 
 
 
 
                                 a l l _ p u r c h a s e s _ e v e r   =   d b . q u e r y ( P u r c h a s e ) . f i l t e r ( P u r c h a s e . p r o d u c t _ i d   = =   p r o d u c t . i d ) . a l l ( ) 
 
                                 a l l _ s a l e s _ e v e r   =   d b . q u e r y ( S a l e ) . f i l t e r ( S a l e . p r o d u c t _ i d   = =   p r o d u c t . i d ) . a l l ( ) 
 
                                 t o t a l _ p u r c h a s e s _ e v e r   =   s u m ( p . q u a n t i t y   f o r   p   i n   a l l _ p u r c h a s e s _ e v e r ) 
 
                                 t o t a l _ s a l e s _ e v e r   =   s u m ( s . q u a n t i t y   f o r   s   i n   a l l _ s a l e s _ e v e r ) 
 
 
 
                                 o p e n i n g _ s t o c k   =   p r o d u c t . s t o c k   +   t o t a l _ s a l e s _ e v e r   -   t o t a l _ p u r c h a s e s _ e v e r 
 
                                 c a l c u l a t e d _ s t o c k   =   o p e n i n g _ s t o c k   +   t o t a l _ p u r c h a s e s _ u p _ t o _ d a t e   -   t o t a l _ s a l e s _ u p _ t o _ d a t e 
 
 
 
                         p u r c h a s e _ p r i c e   =   p r o d u c t . p u r c h a s e _ p r i c e 
 
                         s t o c k _ v a l u e   =   p u r c h a s e _ p r i c e   *   c a l c u l a t e d _ s t o c k 
 
 
 
                         s n a p s h o t s . a p p e n d ( P r o d u c t S t o c k S n a p s h o t ( 
 
                                 p r o d u c t _ i d = p r o d u c t . i d , 
 
                                 p r o d u c t _ n a m e = p r o d u c t . n a m e , 
 
                                 p r i c e = p u r c h a s e _ p r i c e , 
 
                                 s t o c k = c a l c u l a t e d _ s t o c k , 
 
                                 s t o c k _ v a l u e = s t o c k _ v a l u e , 
 
                                 u n i t _ t y p e = p r o d u c t . u n i t _ t y p e , 
 
                                 l a s t _ u p d a t e d = d a t e t i m e . n o w ( I S T ) 
 
                         ) ) 
 
 
 
                 p r i n t ( f " â S&   G e n e r a t e d   { l e n ( s n a p s h o t s ) }   s t o c k   s n a p s h o t s " ) 
 
                 r e t u r n   s n a p s h o t s 
 
 
 
         e x c e p t   E x c e p t i o n   a s   e : 
 
                 p r i n t ( f " â  R  E r r o r   g e n e r a t i n g   s t o c k   s n a p s h o t :   { e } " ) 
 
                 r a i s e   H T T P E x c e p t i o n ( s t a t u s _ c o d e = 5 0 0 ,   d e t a i l = f " E r r o r   g e n e r a t i n g   s t o c k   d a t a :   { s t r ( e ) } " ) 
 
 
 
 @ a p p . p o s t ( " / s a l e s / " ,   r e s p o n s e _ m o d e l = S a l e R e s p o n s e ,   s t a t u s _ c o d e = s t a t u s . H T T P _ 2 0 1 _ C R E A T E D ) 
 
 d e f   r e c o r d _ s a l e ( s a l e :   S a l e C r e a t e ,   d b :   S e s s i o n   =   D e p e n d s ( g e t _ d b ) ,   u s e r n a m e :   s t r   =   D e p e n d s ( v e r i f y _ t o k e n ) ) : 
 
         c h e c k _ p e r m i s s i o n ( P e r m i s s i o n . S A L E S ,   d b ,   u s e r n a m e ) 
 
         p r o d u c t   =   d b . q u e r y ( P r o d u c t ) . f i l t e r ( P r o d u c t . i d   = =   s a l e . p r o d u c t _ i d ) . f i r s t ( ) 
 
         i f   n o t   p r o d u c t : 
 
                 r a i s e   H T T P E x c e p t i o n ( s t a t u s _ c o d e = s t a t u s . H T T P _ 4 0 4 _ N O T _ F O U N D ,   d e t a i l = " P r o d u c t   n o t   f o u n d " ) 
 
         i f   p r o d u c t . s t o c k   <   s a l e . q u a n t i t y : 
 
                 r a i s e   H T T P E x c e p t i o n ( s t a t u s _ c o d e = s t a t u s . H T T P _ 4 0 0 _ B A D _ R E Q U E S T ,   d e t a i l = " N o t   e n o u g h   s t o c k   a v a i l a b l e " ) 
 
 
 
         s e l l i n g _ p r i c e   =   p r o d u c t . s e l l i n g _ p r i c e 
 
         t o t a l _ a m o u n t   =   s e l l i n g _ p r i c e   *   s a l e . q u a n t i t y 
 
 
 
         d b _ s a l e   =   S a l e ( 
 
                 p r o d u c t _ i d = s a l e . p r o d u c t _ i d , 
 
                 q u a n t i t y = s a l e . q u a n t i t y , 
 
                 t o t a l _ a m o u n t = t o t a l _ a m o u n t , 
 
                 s a l e _ d a t e = d a t e t i m e . n o w ( I S T ) , 
 
                 c r e a t e d _ b y = d b . q u e r y ( U s e r ) . f i l t e r ( U s e r . u s e r n a m e   = =   u s e r n a m e ) . f i r s t ( ) . i d 
 
         ) 
 
         p r o d u c t . s t o c k   - =   s a l e . q u a n t i t y 
 
 
 
         d b . a d d ( d b _ s a l e ) 
 
         d b . c o m m i t ( ) 
 
         d b . r e f r e s h ( d b _ s a l e ) 
 
         r e t u r n   d b _ s a l e 
 
 
 
 @ a p p . p o s t ( " / p u r c h a s e s / " ,   r e s p o n s e _ m o d e l = P u r c h a s e R e s p o n s e ,   s t a t u s _ c o d e = s t a t u s . H T T P _ 2 0 1 _ C R E A T E D ) 
 
 d e f   r e c o r d _ p u r c h a s e ( p u r c h a s e :   P u r c h a s e C r e a t e ,   d b :   S e s s i o n   =   D e p e n d s ( g e t _ d b ) ,   u s e r n a m e :   s t r   =   D e p e n d s ( v e r i f y _ t o k e n ) ) : 
 
         c h e c k _ p e r m i s s i o n ( P e r m i s s i o n . P U R C H A S E ,   d b ,   u s e r n a m e ) 
 
         p r o d u c t   =   d b . q u e r y ( P r o d u c t ) . f i l t e r ( P r o d u c t . i d   = =   p u r c h a s e . p r o d u c t _ i d ) . f i r s t ( ) 
 
         i f   n o t   p r o d u c t : 
 
                 r a i s e   H T T P E x c e p t i o n ( s t a t u s _ c o d e = s t a t u s . H T T P _ 4 0 4 _ N O T _ F O U N D ,   d e t a i l = " P r o d u c t   n o t   f o u n d " ) 
 
 
 
         t o t a l _ c o s t   =   p u r c h a s e . u n i t _ c o s t   *   p u r c h a s e . q u a n t i t y 
 
         d b _ p u r c h a s e   =   P u r c h a s e ( 
 
                 p r o d u c t _ i d = p u r c h a s e . p r o d u c t _ i d , 
 
                 q u a n t i t y = p u r c h a s e . q u a n t i t y , 
 
                 t o t a l _ c o s t = t o t a l _ c o s t , 
 
                 p u r c h a s e _ d a t e = d a t e t i m e . n o w ( I S T ) , 
 
                 c r e a t e d _ b y = d b . q u e r y ( U s e r ) . f i l t e r ( U s e r . u s e r n a m e   = =   u s e r n a m e ) . f i r s t ( ) . i d 
 
         ) 
 
         p r o d u c t . s t o c k   + =   p u r c h a s e . q u a n t i t y 
 
 
 
         d b . a d d ( d b _ p u r c h a s e ) 
 
         d b . c o m m i t ( ) 
 
         d b . r e f r e s h ( d b _ p u r c h a s e ) 
 
         r e t u r n   d b _ p u r c h a s e 
 
