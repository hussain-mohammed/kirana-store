# This file contains the missing API endpoints - append this to api/main.py

from datetime import datetime, timezone, timedelta
import os
import jwt
import bcrypt
from typing import List, Optional
from fastapi import FastAPI, HTTPException, status, Depends
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from fastapi.responses import JSONResponse
from sqlalchemy import text
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session
import enum

# Import models and functions from main.py
from main import User, Product, Sale, Purchase, get_db, app, ProductCreate, ProductResponse, SaleCreate, SaleResponse, PurchaseCreate, PurchaseResponse, ProductStockSnapshot, LoginRequest, UserResponse, LoginResponse

# JWT Secret Key
SECRET_KEY_JWT = os.getenv("SECRET_KEY", "your-secret-key-change-this-in-production")

# Initialize the HTTPBearer instance
security = HTTPBearer()

# IST timezone
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

def check_permission(permission: Permission, db, username: str):
    """Check if user has the required permission"""
    user = db.query(User).filter(User.username == username).first()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")

    permission_attr = permission.value
    if not getattr(user, permission_attr, False):
        raise HTTPException(status_code=403, detail=f"Permission denied: {permission.value}")

def authenticate_user(db, username: str, password: str):
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

# --- API Endpoint to serve products to the frontend ---
@app.get("/products")
async def get_products(db: Session = Depends(get_db)):
    """Returns the list of real products from database for the frontend to display."""
    try:
        db_products = db.query(Product).all()
        print(f"📦 Found {len(db_products)} products in database")

        frontend_products = []

        for product in db_products:
            frontend_products.append({
                "id": product.id,
                "name": product.name,
                "price": float(product.selling_price),  # Use selling_price for frontend display
                "purchase_price": float(product.purchase_price),
                "selling_price": float(product.selling_price),
                "unit_type": str(product.unit_type),  # Ensure it's returned as string
                "imageUrl": "",  # Let frontend generate dynamic images
                "stock": product.stock
            })

        print("✅ Successfully formatted products for frontend")
        return JSONResponse(content=frontend_products, media_type="application/json")

    except Exception as e:
        print(f"❌ Error fetching products: {e}")
        fallback_products = [
            {"id": 1, "name": "Apple", "price": 100.00, "imageUrl": "https://placehold.co/400x400/81c784/ffffff?text=Apple", "stock": 50},
            {"id": 2, "name": "Banana", "price": 50.00, "imageUrl": "https://placehold.co/400x400/fff176/ffffff?text=Banana", "stock": 30},
        ]
        return JSONResponse(content=fallback_products, media_type="application/json")

# --- API Endpoints for Products (DB operations) ---
@app.post("/products/", response_model=ProductResponse, status_code=status.HTTP_201_CREATED)
def create_product(product: ProductCreate, db: Session = Depends(get_db)):
    db_product = Product(**product.dict())
    db.add(db_product)
    db.commit()
    db.refresh(db_product)
    return db_product

@app.get("/products/stock-snapshot", response_model=List[ProductStockSnapshot])
def get_products_stock_snapshot(
    date_from: Optional[str] = None,
    date_to: Optional[str] = None,
    product_id: Optional[int] = None,
    db: Session = Depends(get_db)
):
    """
    Get product stock snapshot with date filtering.
    Always shows purchase prices for inventory valuation.
    """
    try:
        print(f"📊 Generating stock snapshot - Date From: {date_from}, Date To: {date_to}, Product ID: {product_id}")

        # Parse date filters
        filter_date_from = None
        filter_date_to = None

        if date_from:
            try:
                try:
                    filter_date_from = datetime.fromisoformat(date_from.replace('Z', '+00:00'))
                except ValueError:
                    if len(date_from) == 10:
                        filter_date_from = datetime.fromisoformat(date_from)
                    else:
                        raise ValueError(f"Unsupported date format: {date_from}")
                print(f"📅 Parsed date_from: {filter_date_from}")
            except ValueError as e:
                print(f"⚠️ Invalid date_from format: {date_from}, error: {e}")

        if date_to:
            try:
                try:
                    filter_date_to = datetime.fromisoformat(date_to.replace('Z', '+00:00'))
                except ValueError:
                    if len(date_to) == 10:
                        filter_date_to = datetime.fromisoformat(date_to)
                    else:
                        raise ValueError(f"Unsupported date format: {date_to}")
                print(f"📅 Parsed date_to: {filter_date_to}")
            except ValueError as e:
                print(f"⚠️ Invalid date_to format: {date_to}, error: {e}")

        # Base query for products
        query = db.query(Product)

        # Filter by product if specified
        if product_id:
            query = query.filter(Product.id == product_id)

        products = query.all()

        snapshots = []
        for product in products:
            calculated_stock = product.stock

            if filter_date_to:
                purchases = db.query(Purchase).filter(
                    Purchase.product_id == product.id,
                    Purchase.purchase_date <= filter_date_to
                ).all()

                sales = db.query(Sale).filter(
                    Sale.product_id == product.id,
                    Sale.sale_date <= filter_date_to
                ).all()

                total_purchases_up_to_date = sum(p.quantity for p in purchases)
                total_sales_up_to_date = sum(s.quantity for s in sales)

                all_purchases_ever = db.query(Purchase).filter(Purchase.product_id == product.id).all()
                all_sales_ever = db.query(Sale).filter(Sale.product_id == product.id).all()
                total_purchases_ever = sum(p.quantity for p in all_purchases_ever)
                total_sales_ever = sum(s.quantity for s in all_sales_ever)

                opening_stock = product.stock + total_sales_ever - total_purchases_ever
                calculated_stock = opening_stock + total_purchases_up_to_date - total_sales_up_to_date

            purchase_price = product.purchase_price
            stock_value = purchase_price * calculated_stock

            snapshots.append(ProductStockSnapshot(
                product_id=product.id,
                product_name=product.name,
                price=purchase_price,
                stock=calculated_stock,
                stock_value=stock_value,
                unit_type=product.unit_type,
                last_updated=datetime.now(IST)
            ))

        print(f"✅ Generated {len(snapshots)} stock snapshots")
        return snapshots

    except Exception as e:
        print(f"❌ Error generating stock snapshot: {e}")
        raise HTTPException(status_code=500, detail=f"Error generating stock data: {str(e)}")

@app.post("/sales/", response_model=SaleResponse, status_code=status.HTTP_201_CREATED)
def record_sale(sale: SaleCreate, db: Session = Depends(get_db), username: str = Depends(verify_token)):
    check_permission(Permission.SALES, db, username)
    product = db.query(Product).filter(Product.id == sale.product_id).first()
    if not product:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Product not found")
    if product.stock < sale.quantity:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Not enough stock available")

    selling_price = product.selling_price
    total_amount = selling_price * sale.quantity

    db_sale = Sale(
        product_id=sale.product_id,
        quantity=sale.quantity,
        total_amount=total_amount,
        sale_date=datetime.now(IST),
        created_by=db.query(User).filter(User.username == username).first().id
    )
    product.stock -= sale.quantity

    db.add(db_sale)
    db.commit()
    db.refresh(db_sale)
    return db_sale

@app.post("/purchases/", response_model=PurchaseResponse, status_code=status.HTTP_201_CREATED)
def record_purchase(purchase: PurchaseCreate, db: Session = Depends(get_db), username: str = Depends(verify_token)):
    check_permission(Permission.PURCHASE, db, username)
    product = db.query(Product).filter(Product.id == purchase.product_id).first()
    if not product:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Product not found")

    total_cost = purchase.unit_cost * purchase.quantity
    db_purchase = Purchase(
        product_id=purchase.product_id,
        quantity=purchase.quantity,
        total_cost=total_cost,
        purchase_date=datetime.now(IST),
        created_by=db.query(User).filter(User.username == username).first().id
    )
    product.stock += purchase.quantity

    db.add(db_purchase)
    db.commit()
    db.refresh(db_purchase)
    return db_purchase

# --- Authentication endpoints ---
@app.post("/auth/register", response_model=UserResponse)
async def register_user(
    user_data: LoginRequest,
    db: Session = Depends(get_db)
):
    try:
        username = user_data.username
        password = user_data.password
        email = username + "@example.com"

        if not username or not password:
            raise HTTPException(status_code=400, detail="Username and password are required")

        if len(password) < 6:
            raise HTTPException(status_code=400, detail="Password must be at least 6 characters long")

        existing_user = db.query(User).filter(
            (User.username == username) | (User.email == email)
        ).first()
        if existing_user:
            raise HTTPException(status_code=400, detail="Username or email already exists")

        hashed_password = bcrypt.hashpw(password.encode('utf-8'), bcrypt.gensalt())

        new_user = User(
            username=username,
            email=email,
            password_hash=hashed_password.decode('utf-8'),
            sales=True,
            purchase=True,
            create_product=False,
            delete_product=False,
            sales_ledger=False,
            purchase_ledger=False,
            stock_ledger=False,
            profit_loss=False,
            opening_stock=False,
            user_management=False,
            is_active=True
        )

        db.add(new_user)
        db.commit()
        db.refresh(new_user)

        permissions = [
            k for k, v in {
                "sales": new_user.sales,
                "purchase": new_user.purchase,
                "create_product": new_user.create_product,
                "delete_product": new_user.delete_product,
                "sales_ledger": new_user.sales_ledger,
                "purchase_ledger": new_user.purchase_ledger,
                "stock_ledger": new_user.stock_ledger,
                "profit_loss": new_user.profit_loss,
                "opening_stock": new_user.opening_stock,
                "user_management": new_user.user_management,
            }.items() if v
        ]

        return UserResponse(
            id=new_user.id,
            username=new_user.username,
            email=new_user.email,
            is_active=new_user.is_active,
            permissions=permissions
        )
    except HTTPException:
        db.rollback()
        raise
    except SQLAlchemyError as e:
        db.rollback()
        raise HTTPException(status_code=500, detail=f"Database error: {str(e)}")

@app.post("/auth/login", response_model=LoginResponse)
async def login(login_data: LoginRequest, db: Session = Depends(get_db)):
    try:
        user = authenticate_user(db, login_data.username, login_data.password)
        if not user:
            raise HTTPException(status_code=401, detail="Invalid username or password")

        user.last_login = datetime.now(IST)
        db.commit()

        access_token = create_access_token({"sub": user.username})

        permissions = [
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

        user_response = UserResponse(
            id=user.id,
            username=user.username,
            email=user.email,
            is_active=user.is_active,
            permissions=permissions
        )

        return LoginResponse(
            access_token=access_token,
            token_type="bearer",
            user=user_response
        )
    except HTTPException:
        raise
    except Exception as e:
        print(f"Login error for user {login_data.username}: {str(e)}")
        raise HTTPException(status_code=500, detail="Internal server error during login")

@app.get("/auth/me", response_model=UserResponse)
async def get_current_user(username: str = Depends(verify_token), db: Session = Depends(get_db)):
    user = db.query(User).filter(User.username == username).first()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")

    permissions = [
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

    return UserResponse(
        id=user.id,
        username=user.username,
        email=user.email,
        is_active=user.is_active,
        permissions=permissions
    )

@app.post("/auth/logout")
async def logout(username: str = Depends(verify_token)):
    return {"message": "Logged out successfully"}

# --- Health Check Endpoints ---
@app.get("/")
async def root():
    return {
        "message": "Kirana Store API is running",
        "status": "active",
        "timestamp": datetime.now(IST).isoformat()
    }

@app.get("/health")
async def health_check(db: Session = Depends(get_db)):
    try:
        db.execute(text("SELECT 1"))
        return {
            "status": "healthy",
            "database": "connected",
            "timestamp": datetime.now(IST).isoformat()
        }
    except Exception as e:
        return {
            "status": "unhealthy",
            "database": "disconnected",
            "error": str(e)
        }

# Pydantic models (must be imported before this file from main.py)
# These are required for the API endpoints to work

# Assuming these models are imported from main.py, but listing them here for completeness:

# class ProductBase(BaseModel):
#     name: str
#     purchase_price: float = Field(..., gt=0)
#     selling_price: float = Field(..., gt=0)
#     unit_type: str = Field(...)

# class ProductCreate(ProductBase):
#     stock: int = Field(0, ge=0)

# class ProductResponse(ProductCreate):
#     id: int
#     created_at: datetime

# class SaleCreate(BaseModel):
#     product_id: int
#     quantity: int = Field(..., gt=0)

# class SaleResponse(BaseModel):
#     id: int
#     product_id: int
#     quantity: int
#     total_amount: float
#     sale_date: datetime

# class PurchaseCreate(BaseModel):
#     product_id: int
#     quantity: int = Field(..., gt=0)
#     unit_cost: float = Field(..., gt=0)

# class PurchaseResponse(BaseModel):
#     id: int
#     product_id: int
#     quantity: int
#     total_cost: float
#     purchase_date: datetime

# class ProductStockSnapshot(BaseModel):
#     product_id: int
#     product_name: str
#     price: float
#     stock: int
#     stock_value: float
#     unit_type: str
#     last_updated: datetime

# class LoginRequest(BaseModel):
#     username: str
#     password: str

# class UserResponse(BaseModel):
#     id: int
#     username: str
#     email: str
#     is_active: bool
#     permissions: Optional[List[str]] = None

# class LoginResponse(BaseModel):
#     access_token: str
#     token_type: str
#     user: UserResponse

# Database models (must be imported from main.py):
# - User
# - Product
# - Sale
# - Purchase
# - get_db dependency

# Add Vercel handler at the end
from mangum import Mangum

# This line will cause an error since 'app' is not defined in this module
# It should be imported from main.py, and the Vercel handler should be in main.py
# handler = Mangum(app)
print("Note: Vercel handler should be in main.py, not in missing_endpoints.py")

# if __name__ == "__main__":
#     import uvicorn
#     port = int(os.environ.get("PORT", 8000))
#     uvicorn.run(app, host="0.0.0.0", port=port)
