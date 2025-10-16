import json
from datetime import datetime, timezone, timedelta
import os
from typing import List, Optional, Any, Dict

# Load environment variables
from dotenv import load_dotenv
load_dotenv()

from fastapi import FastAPI, HTTPException, Request, status, Depends, Form
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from pydantic import BaseModel, Field
from sqlalchemy import create_engine, Column, Integer, String, Float, DateTime, Boolean, text, ForeignKey
from sqlalchemy.orm import declarative_base, sessionmaker, Session
from sqlalchemy.exc import SQLAlchemyError
import enum
import jwt
import bcrypt
from fastapi.responses import JSONResponse, HTMLResponse, FileResponse
from fastapi.middleware.cors import CORSMiddleware
from twilio.twiml.messaging_response import MessagingResponse

# --- Database Configuration ---
DATABASE_URL = os.getenv("DATABASE_URL")
if not DATABASE_URL:
    DATABASE_URL = "sqlite:///kirana.db"  # fallback

engine = create_engine(DATABASE_URL, connect_args={"check_same_thread": False} if "sqlite" in DATABASE_URL else {})
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

Base = declarative_base()

# --- Models ---
IST = timezone(timedelta(hours=5, minutes=30))

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

class User(Base):
    __tablename__ = "users"
    id = Column(Integer, primary_key=True, index=True)
    username = Column(String, unique=True, index=True, nullable=False)
    email = Column(String, unique=True, index=True, nullable=False)
    password_hash = Column(String, nullable=False)
    sales = Column(Boolean, default=True)
    purchase = Column(Boolean, default=True)
    create_product = Column(Boolean, default=False)
    delete_product = Column(Boolean, default=False)
    sales_ledger = Column(Boolean, default=False)
    purchase_ledger = Column(Boolean, default=False)
    stock_ledger = Column(Boolean, default=False)
    profit_loss = Column(Boolean, default=False)
    opening_stock = Column(Boolean, default=False)
    user_management = Column(Boolean, default=False)
    is_active = Column(Boolean, default=True)
    created_at = Column(DateTime, default=lambda: datetime.now(IST))

class Product(Base):
    __tablename__ = "products"
    id = Column(Integer, primary_key=True, index=True)
    name = Column(String, unique=True, index=True, nullable=False)
    purchase_price = Column(Float, nullable=False)
    selling_price = Column(Float, nullable=False)
    unit_type = Column(String, nullable=False)
    stock = Column(Integer, default=0)
    created_at = Column(DateTime, default=lambda: datetime.now(IST))

class Sale(Base):
    __tablename__ = "sales"
    id = Column(Integer, primary_key=True, index=True)
    product_id = Column(Integer, ForeignKey("products.id"), nullable=True)
    quantity = Column(Integer, nullable=False)
    total_amount = Column(Float, nullable=False)
    sale_date = Column(DateTime, default=lambda: datetime.now(IST))

class Purchase(Base):
    __tablename__ = "purchases"
    id = Column(Integer, primary_key=True, index=True)
    product_id = Column(Integer, ForeignKey("products.id"), nullable=True)
    quantity = Column(Integer, nullable=False)
    total_cost = Column(Float, nullable=False)
    purchase_date = Column(DateTime, default=lambda: datetime.now(IST))

# --- Pydantic Models ---
class ProductResponse(BaseModel):
    id: int
    name: str
    purchase_price: float
    selling_price: float
    unit_type: str
    stock: int
    created_at: datetime

class LoginRequest(BaseModel):
    username: str
    password: str

class LoginResponse(BaseModel):
    access_token: str
    token_type: str
    user: Dict

# --- FastAPI App Setup ---
app = FastAPI(title="Kirana Store API", version="1.0.0")

# CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# --- Database Dependency ---
def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

# --- Authentication ---
SECRET_KEY = os.getenv("SECRET_KEY", "your-secret-key")
security = HTTPBearer(auto_error=False)

def authenticate_user(db: Session, username: str, password: str):
    user = db.query(User).filter(User.username == username).first()
    if not user or not bcrypt.checkpw(password.encode('utf-8'), user.password_hash.encode('utf-8')):
        return None
    return user

def create_access_token(data: dict):
    expire = datetime.utcnow() + timedelta(hours=24)
    to_encode = data.copy()
    to_encode.update({"exp": expire})
    encoded_jwt = jwt.encode(to_encode, SECRET_KEY, algorithm="HS256")
    return encoded_jwt

def verify_token(credentials: HTTPAuthorizationCredentials = Depends(security)):
    if not credentials:
        return None
    try:
        payload = jwt.decode(credentials.credentials, SECRET_KEY, algorithms=["HS256"])
        return payload.get("sub")
    except:
        return None

def check_permission(required_permission: Permission, db: Session, username: str):
    user = db.query(User).filter(User.username == username).first()
    if not user or not getattr(user, required_permission.value, False):
        raise HTTPException(status_code=403, detail=f"Permission required: {required_permission.value}")

# --- Create Tables on Startup ---
Base.metadata.create_all(bind=engine)

# --- API Routes ---
@app.get("/")
async def root():
    return {"message": "Kirana Store API is running", "status": "active"}

@app.get("/health")
async def health_check(db: Session = Depends(get_db)):
    try:
        db.execute(text("SELECT 1"))
        return {"status": "healthy", "database": "connected"}
    except Exception as e:
        return {"status": "unhealthy", "error": str(e)}

@app.get("/products")
async def get_products(db: Session = Depends(get_db)):
    try:
        products = db.query(Product).all()
        product_list = []
        for p in products:
            product_list.append({
                "id": p.id,
                "name": p.name,
                "purchase_price": float(p.purchase_price),
                "selling_price": float(p.selling_price),
                "unit_type": p.unit_type,
                "stock": p.stock,
                "imageUrl": "",
            })
        return JSONResponse(content=product_list)
    except Exception as e:
        print(f"Error fetching products: {e}")
        return JSONResponse(content=[])

@app.post("/auth/login")
async def login(login_data: LoginRequest, db: Session = Depends(get_db)):
    user = authenticate_user(db, login_data.username, login_data.password)
    if not user:
        raise HTTPException(status_code=401, detail="Invalid credentials")

    access_token = create_access_token({"sub": user.username})

    return LoginResponse(
        access_token=access_token,
        token_type="bearer",
        user={
            "id": user.id,
            "username": user.username,
            "email": user.email,
            "is_active": user.is_active,
            "permissions": [
                k for k, v in {
                    "sales": user.sales,
                    "purchase": user.purchase,
                    "create_product": user.create_product,
                    "delete_product": user.delete_product,
                    "sales_ledger": user.sales_ledger,
                    "purchase_ledger": user.purchase_ledger,
                    "stock_ledger": user.stock_ledger,
                    "profit_loss": user.profit_loss,
                    "opening_stock": user.opening_stock,
                    "user_management": user.user_management,
                }.items() if v
            ]
        }
    )

# --- Vercel Serverless Handler ---
from mangum import Mangum

handler = Mangum(app, lifespan="off")

# For testing locally
if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
