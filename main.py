from datetime import datetime, timezone, timedelta
import os
from contextlib import asynccontextmanager
from typing import List, Optional, Any, Dict
from dotenv import load_dotenv
from fastapi import FastAPI, HTTPException, Request, status, Depends
from pydantic import BaseModel, Field
from sqlalchemy import create_engine, Column, Integer, String, Float, DateTime, text
from sqlalchemy.orm import declarative_base, sessionmaker, Session, relationship
from sqlalchemy import ForeignKey
from twilio.twiml.messaging_response import MessagingResponse
from fastapi.responses import JSONResponse
from fastapi.middleware.cors import CORSMiddleware

# Load environment variables from .env file for local development
load_dotenv()

DATABASE_URL = os.getenv("DATABASE_URL")
if not DATABASE_URL:
        print("WARNING: DATABASE_URL not set in environment variables. Using default PostgreSQL database.")

# Create a SQLAlchemy engine
engine = create_engine(DATABASE_URL)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

# Base class for declarative models
Base = declarative_base()

# --- Database Models ---
IST = timezone(timedelta(hours=5, minutes=30))

class Product(Base):
    """Represents a product in the store."""
    __tablename__ = "products"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String, unique=True, index=True, nullable=False)
    price = Column(Float, nullable=False)
    stock = Column(Integer, default=0)

class Sale(Base):
    """Records a single sale transaction."""
    __tablename__ = "sales"

    id = Column(Integer, primary_key=True, index=True)
    product_id = Column(Integer, ForeignKey("products.id"))
    quantity = Column(Integer, nullable=False)
    total_amount = Column(Float, nullable=False)
    sale_date = Column(DateTime, default=lambda: datetime.now(IST))
    product = relationship("Product")

class Purchase(Base):
    """Records a purchase of stock from a supplier."""
    __tablename__ = "purchases"

    id = Column(Integer, primary_key=True, index=True)
    product_id = Column(Integer, ForeignKey("products.id"))
    quantity = Column(Integer, nullable=False)
    total_cost = Column(Float, nullable=False)
    purchase_date = Column(DateTime, default=lambda: datetime.now(IST))
    product = relationship("Product")

# --- Pydantic Models for API Requests/Responses ---
class ProductBase(BaseModel):
    name: str
    price: float = Field(..., gt=0, description="Price must be a positive number")

class ProductCreate(ProductBase):
    stock: int = Field(0, ge=0, description="Initial stock level")

class ProductUpdate(BaseModel):
    name: Optional[str] = None
    price: Optional[float] = None
    stock: Optional[int] = None

class ProductResponse(ProductCreate):
    id: int

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
    last_updated: datetime


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
    Base.metadata.create_all(bind=engine)
    print("Database tables created.")
    
    # Seed with sample data if no products exist
    db = SessionLocal()
    try:
        product_count = db.query(Product).count()
        if product_count == 0:
            print("Seeding database with sample products...")
            sample_products = [
                Product(name="Apple", price=100.00, stock=50),
                Product(name="Banana", price=50.00, stock=30),
                Product(name="Orange", price=80.00, stock=25),
                Product(name="Milk", price=65.00, stock=20),
                Product(name="Bread", price=40.00, stock=15),
                Product(name="Eggs", price=90.00, stock=40),
                Product(name="Rice", price=120.00, stock=60),
                Product(name="Sugar", price=55.00, stock=35),
            ]
            db.add_all(sample_products)
            db.commit()
            print("Sample products added to database.")
        else:
            print(f"Database already contains {product_count} products.")
    finally:
        db.close()
    
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

# === YOUR ORIGINAL ENDPOINTS ===

# --- API Endpoint to serve products to the frontend ---
@app.get("/products")
def get_products(db: Session = Depends(get_db)):
    """Returns the list of real products from database for the frontend to display."""
    try:
        db_products = db.query(Product).all()
        print(f"📦 Found {len(db_products)} products in database")
        
        frontend_products = []
        image_mapping = {
            "apple": "https://placehold.co/400x400/81c784/ffffff?text=Apple",
            "banana": "https://placehold.co/400x400/fff176/ffffff?text=Banana",
            "orange": "https://placehold.co/400x400/ffb74d/ffffff?text=Orange",
            "milk": "https://placehold.co/400x400/b0e0e6/ffffff?text=Milk",
            "bread": "https://placehold.co/400x400/d7ccc8/ffffff?text=Bread",
            "eggs": "https://placehold.co/400x400/fff9c4/ffffff?text=Eggs",
            "rice": "https://placehold.co/400x400/f0f8ff/ffffff?text=Rice",
            "sugar": "https://placehold.co/400x400/e6e6e6/ffffff?text=Sugar"
        }
        
        for product in db_products:
            image_url = image_mapping.get(product.name.lower(), "https://placehold.co/400x400/cccccc/ffffff?text=Product")
            
            frontend_products.append({
                "id": product.id,
                "name": product.name,
                "price": float(product.price),
                "imageUrl": image_url,
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

@app.get("/products/{product_id}", response_model=ProductResponse)
def get_product(product_id: int, db: Session = Depends(get_db)):
    db_product = db.query(Product).filter(Product.id == product_id).first()
    if db_product is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Product not found")
    return db_product

@app.put("/products/{product_id}", response_model=ProductResponse)
def update_product(product_id: int, product_data: ProductUpdate, db: Session = Depends(get_db)):
    db_product = db.query(Product).filter(Product.id == product_id).first()
    if db_product is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Product not found")

    for key, value in product_data.dict(exclude_unset=True).items():
        setattr(db_product, key, value)
    
    db.commit()
    db.refresh(db_product)
    return db_product

@app.delete("/products/{product_id}", status_code=status.HTTP_200_OK)
def delete_product(product_id: int, db: Session = Depends(get_db)):
    """
    Delete a product and all its associated sales and purchase records.
    """
    try:
        # Find the product
        db_product = db.query(Product).filter(Product.id == product_id).first()
        if db_product is None:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Product not found")
        
        # Get product name for response message
        product_name = db_product.name
        
        # Delete all associated sales records first
        sales_count = db.query(Sale).filter(Sale.product_id == product_id).count()
        if sales_count > 0:
            db.query(Sale).filter(Sale.product_id == product_id).delete()
            print(f"Deleted {sales_count} sales records for product {product_name}")
        
        # Delete all associated purchase records
        purchases_count = db.query(Purchase).filter(Purchase.product_id == product_id).count()
        if purchases_count > 0:
            db.query(Purchase).filter(Purchase.product_id == product_id).delete()
            print(f"Deleted {purchases_count} purchase records for product {product_name}")
        
        # Now delete the product
        db.delete(db_product)
        db.commit()
        
        return {
            "status": "success",
            "message": f"Product '{product_name}' deleted successfully. Removed {sales_count} sales and {purchases_count} purchases.",
            "product_id": product_id,
            "sales_deleted": sales_count,
            "purchases_deleted": purchases_count
        }
        
    except Exception as e:
        db.rollback()
        print(f"Error deleting product {product_id}: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, 
            detail=f"Error deleting product: {str(e)}"
        )
# --- API Endpoints for Sales ---
@app.post("/sales/", response_model=SaleResponse, status_code=status.HTTP_201_CREATED)
def record_sale(sale: SaleCreate, db: Session = Depends(get_db)):
    product = db.query(Product).filter(Product.id == sale.product_id).first()
    if not product:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Product not found")
    if product.stock < sale.quantity:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Not enough stock available")

    total_amount = product.price * sale.quantity
    db_sale = Sale(
        product_id=sale.product_id,
        quantity=sale.quantity,
        total_amount=total_amount,
        sale_date=datetime.now(IST)
    )
    product.stock -= sale.quantity
    
    db.add(db_sale)
    db.commit()
    db.refresh(db_sale)
    return db_sale

# --- API Endpoints for Purchases ---
@app.post("/purchases/", response_model=PurchaseResponse, status_code=status.HTTP_201_CREATED)
def record_purchase(purchase: PurchaseCreate, db: Session = Depends(get_db)):
    product = db.query(Product).filter(Product.id == purchase.product_id).first()
    if not product:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Product not found")

    total_cost = purchase.unit_cost * purchase.quantity
    db_purchase = Purchase(
        product_id=purchase.product_id,
        quantity=purchase.quantity,
        total_cost=total_cost,
        purchase_date=datetime.now(IST)
    )
    product.stock += purchase.quantity
    
    db.add(db_purchase)
    db.commit()
    db.refresh(db_purchase)
    return db_purchase

# --- ADD DELETE ENDPOINTS FOR SALES AND PURCHASES ---

@app.delete("/sales/{sale_id}", status_code=status.HTTP_200_OK)
def delete_sale(sale_id: int, db: Session = Depends(get_db)):
    """
    Delete a sale record and restore product stock.
    """
    try:
        # Find the sale record
        db_sale = db.query(Sale).filter(Sale.id == sale_id).first()
        if not db_sale:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Sale record not found")
        
        # Find the product
        product = db.query(Product).filter(Product.id == db_sale.product_id).first()
        if not product:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Product not found")
        
        # Restore the stock
        product.stock += db_sale.quantity
        
        # Delete the sale record
        db.delete(db_sale)
        db.commit()
        
        return {
            "status": "success",
            "message": f"Sale record deleted successfully. Restored {db_sale.quantity} units to {product.name} stock.",
            "sale_id": sale_id
        }
        
    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=f"Error deleting sale: {str(e)}")

@app.delete("/purchases/{purchase_id}", status_code=status.HTTP_200_OK)
def delete_purchase(purchase_id: int, db: Session = Depends(get_db)):
    """
    Delete a purchase record and adjust product stock.
    """
    try:
        # Find the purchase record
        db_purchase = db.query(Purchase).filter(Purchase.id == purchase_id).first()
        if not db_purchase:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Purchase record not found")
        
        # Find the product
        product = db.query(Product).filter(Product.id == db_purchase.product_id).first()
        if not product:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Product not found")
        
        # Check if we have enough stock to remove
        if product.stock < db_purchase.quantity:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST, 
                detail=f"Cannot delete purchase. Current stock ({product.stock}) is less than purchase quantity ({db_purchase.quantity})"
            )
        
        # Remove the purchased stock
        product.stock -= db_purchase.quantity
        
        # Delete the purchase record
        db.delete(db_purchase)
        db.commit()
        
        return {
            "status": "success",
            "message": f"Purchase record deleted successfully. Removed {db_purchase.quantity} units from {product.name} stock.",
            "purchase_id": purchase_id
        }
        
    except HTTPException:
        db.rollback()
        raise
    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=f"Error deleting purchase: {str(e)}")

# --- API Endpoint for WhatsApp Orders ---
@app.post("/whatsapp-order/", status_code=status.HTTP_200_OK)
def process_whatsapp_order(order_request: WhatsAppOrderRequest, db: Session = Depends(get_db)):
    """Simulates receiving an order from a WhatsApp webhook."""
    total_bill = 0
    items_sold = []
    
    for item in order_request.items:
        product = db.query(Product).filter(Product.name.ilike(item.product_name)).first()
        if not product:
            return {"status": "error", "message": f"Product '{item.product_name}' not found."}
        
        if product.stock < item.quantity:
            return {"status": "error", "message": f"Insufficient stock for '{item.product_name}'."}

        item_total = product.price * item.quantity
        total_bill += item_total
        product.stock -= item.quantity
        
        db_sale = Sale(
            product_id=product.id,
            quantity=item.quantity,
            total_amount=item_total
        )
        db.add(db_sale)
        items_sold.append(item.product_name)
    
    db.commit()
    
    response_message = (
        f"Thank you, {order_request.customer_name}! Your order for {', '.join(items_sold)} "
        f"has been placed. Your total bill is Rs. {total_bill:.2f}. "
        "We will notify you once the payment is confirmed and the delivery is on its way."
    )
    
    print(f"Online order received from {order_request.customer_name} ({order_request.phone_number}). "
          f"Total bill: Rs. {total_bill:.2f}")

    return {"status": "success", "message": response_message, "total_bill": total_bill}

# --- Dummy product data for SMS handler ---
PRODUCTS_DB = {
    "apple": 100.00,
    "banana": 50.00,
    "orange": 80.00,
    "milk": 65.00,
    "bread": 40.00,
    "eggs": 90.00,
    "rice": 120.00,
    "sugar": 55.00
}

# --- 1. PURCHASE LEDGER - All Purchase Details ---
@app.get("/ledger/purchases", response_model=List[PurchaseLedgerEntry])
def get_purchase_ledger(
    start_date: Optional[str] = None,
    end_date: Optional[str] = None,
    product_id: Optional[int] = None,
    db: Session = Depends(get_db)
):
    """
    Get complete purchase ledger with all purchase details.
    """
    query = db.query(Purchase)
    
    # Apply date filters
    if start_date:
        start_dt = datetime.datetime.fromisoformat(start_date.replace('Z', '+00:00'))
        query = query.filter(Purchase.purchase_date >= start_dt)
    
    if end_date:
        end_dt = datetime.datetime.fromisoformat(end_date.replace('Z', '+00:00'))
        query = query.filter(Purchase.purchase_date <= end_dt)
    
    # Apply product filter
    if product_id:
        query = query.filter(Purchase.product_id == product_id)
    
    # Get purchases ordered by date
    purchases = query.order_by(Purchase.purchase_date.desc()).all()
    
    ledger_entries = []
    for purchase in purchases:
        ledger_entries.append(PurchaseLedgerEntry(
            purchase_id=purchase.id,
            date=purchase.purchase_date,
            product_id=purchase.product_id,
            product_name=purchase.product.name,
            quantity=purchase.quantity,
            unit_cost=purchase.total_cost / purchase.quantity,
            total_cost=purchase.total_cost,
            supplier_info=f"Supplier for {purchase.product.name}"
        ))
    
    return ledger_entries

# --- 2. SALES LEDGER - All Sales Details ---
@app.get("/ledger/sales", response_model=List[SalesLedgerEntry])
def get_sales_ledger(
    start_date: Optional[str] = None,
    end_date: Optional[str] = None,
    product_id: Optional[int] = None,
    db: Session = Depends(get_db)
):
    """
    Get complete sales ledger with all sales details.
    """
    query = db.query(Sale)
    
    # Apply date filters
    if start_date:
        start_dt = datetime.datetime.fromisoformat(start_date.replace('Z', '+00:00'))
        query = query.filter(Sale.sale_date >= start_dt)
    
    if end_date:
        end_dt = datetime.datetime.fromisoformat(end_date.replace('Z', '+00:00'))
        query = query.filter(Sale.sale_date <= end_dt)
    
    # Apply product filter
    if product_id:
        query = query.filter(Sale.product_id == product_id)
    
    # Get sales ordered by date
    sales = query.order_by(Sale.sale_date.desc()).all()
    
    ledger_entries = []
    for sale in sales:
        ledger_entries.append(SalesLedgerEntry(
            sale_id=sale.id,
            date=sale.sale_date,
            product_id=sale.product_id,
            product_name=sale.product.name,
            quantity=sale.quantity,
            unit_price=sale.total_amount / sale.quantity,
            total_amount=sale.total_amount,
            customer_info=f"Customer for {sale.product.name}"
        ))
    
    return ledger_entries

# --- 3. STOCK LEDGER BY PRODUCT - Full History for Specific Product ---
@app.get("/ledger/stock/{product_id}", response_model=ProductStockLedger)
def get_product_stock_ledger(product_id: int, db: Session = Depends(get_db)):
    """
    Get complete stock history for a specific product.
    Shows opening stock, all purchases, all sales, and running balance.
    """
    # Get the product
    product = db.query(Product).filter(Product.id == product_id).first()
    if not product:
        raise HTTPException(status_code=404, detail="Product not found")
    
    # Get all purchases for this product (ordered by date)
    purchases = db.query(Purchase).filter(Purchase.product_id == product_id).order_by(Purchase.purchase_date).all()
    
    # Get all sales for this product (ordered by date)
    sales = db.query(Sale).filter(Sale.product_id == product_id).order_by(Sale.sale_date).all()
    
    # Combine and sort all transactions by date
    all_transactions = []
    
    for purchase in purchases:
        all_transactions.append({
            "date": purchase.purchase_date,
            "type": "PURCHASE",
            "reference": f"Purchase #{purchase.id}",
            "quantity": purchase.quantity,
            "details": f"Purchased {purchase.quantity} units at ₹{purchase.total_cost/purchase.quantity:.2f} each"
        })
    
    for sale in sales:
        all_transactions.append({
            "date": sale.sale_date,
            "type": "SALE", 
            "reference": f"Sale #{sale.id}",
            "quantity": -sale.quantity,  # Negative for sales
            "details": f"Sold {sale.quantity} units at ₹{sale.total_amount/sale.quantity:.2f} each"
        })
    
    # Sort all transactions by date
    all_transactions.sort(key=lambda x: x["date"])
    
    # Calculate running balance
    current_stock = 0
    history = []
    
    # Add opening balance entry
    if all_transactions:
        # Calculate what the opening stock would have been
        total_purchases = sum(p.quantity for p in purchases)
        total_sales = sum(s.quantity for s in sales)
        opening_stock = product.stock + total_sales - total_purchases
        current_stock = opening_stock
    else:
        opening_stock = product.stock
        current_stock = product.stock
    
    # Add opening entry
    history.append(ProductStockHistory(
        date=all_transactions[0]["date"] if all_transactions else datetime.datetime.now(),
        transaction_type="OPENING",
        reference="Opening Stock",
        quantity=opening_stock,
        stock_after_transaction=opening_stock,
        details=f"Opening stock balance"
    ))
    
    # Process each transaction and update running balance
    for transaction in all_transactions:
        current_stock += transaction["quantity"] if transaction["type"] == "PURCHASE" else transaction["quantity"]
        
        history.append(ProductStockHistory(
            date=transaction["date"],
            transaction_type=transaction["type"],
            reference=transaction["reference"],
            quantity=transaction["quantity"],
            stock_after_transaction=current_stock,
            details=transaction["details"]
        ))
    
    return ProductStockLedger(
        product_id=product.id,
        product_name=product.name,
        current_stock=product.stock,
        opening_stock=opening_stock,
        total_purchases=sum(p.quantity for p in purchases),
        total_sales=sum(s.quantity for s in sales),
        history=history
    )

# --- 4. PRODUCT LIST for Stock Ledger Selection ---
@app.get("/ledger/products")
def get_products_for_ledger(db: Session = Depends(get_db)):
    """
    Get list of products with basic info for ledger selection.
    """
    products = db.query(Product).all()
    
    product_list = []
    for product in products:
        # Get purchase and sale counts
        purchase_count = db.query(Purchase).filter(Purchase.product_id == product.id).count()
        sale_count = db.query(Sale).filter(Sale.product_id == product.id).count()
        
        product_list.append({
            "product_id": product.id,
            "product_name": product.name,
            "current_stock": product.stock,
            "price": product.price,
            "total_purchases": purchase_count,
            "total_sales": sale_count,
            "has_activity": purchase_count > 0 or sale_count > 0
        })
    
    return product_list

# --- 5. LEDGER SUMMARY DASHBOARD ---
@app.get("/ledger/summary")
def get_ledger_summary(db: Session = Depends(get_db)):
    """
    Get summary dashboard for all ledgers.
    """
    # Total counts
    total_products = db.query(Product).count()
    total_purchases = db.query(Purchase).count()
    total_sales = db.query(Sale).count()
    
    # Recent activity (last 30 days)
    thirty_days_ago = datetime.datetime.now() - datetime.timedelta(days=30)
    
    recent_purchases = db.query(Purchase).filter(Purchase.purchase_date >= thirty_days_ago).count()
    recent_sales = db.query(Sale).filter(Sale.sale_date >= thirty_days_ago).count()
    
    # Total quantities
    total_purchase_quantity = db.query(Purchase.quantity).all()
    total_purchase_qty = sum([q[0] for q in total_purchase_quantity]) if total_purchase_quantity else 0
    
    total_sale_quantity = db.query(Sale.quantity).all()
    total_sale_qty = sum([q[0] for q in total_sale_quantity]) if total_sale_quantity else 0
    
    # Low stock products
    low_stock_products = db.query(Product).filter(Product.stock <= 10).count()
    
    return {
        "summary": {
            "total_products": total_products,
            "total_purchases": total_purchases,
            "total_sales": total_sales,
            "recent_purchases": recent_purchases,
            "recent_sales": recent_sales,
            "total_purchase_quantity": total_purchase_qty,
            "total_sale_quantity": total_sale_qty,
            "low_stock_products": low_stock_products
        },
        "last_updated": datetime.datetime.now()
    }

@app.get("/products/stock-snapshot", response_model=List[ProductStockSnapshot])
def get_products_stock_snapshot(
    date_from: Optional[str] = None,
    date_to: Optional[str] = None,
    product_id: Optional[int] = None,
    db: Session = Depends(get_db)
):
    """
    Get product stock data with date filtering.
    For date filtering, this returns the stock state at the end of the date range.
    """
    try:
        print(f"📊 Generating stock snapshot - Date From: {date_from}, Date To: {date_to}, Product ID: {product_id}")
        
        # Base query for current products
        query = db.query(Product)
        
        # Filter by product if specified
        if product_id:
            query = query.filter(Product.id == product_id)
        
        products = query.all()
        
        # If no date filters, return current stock
        if not date_from and not date_to:
            print("🔄 No date filters - returning current stock")
            snapshots = []
            for product in products:
                snapshots.append(ProductStockSnapshot(
                    product_id=product.id,
                    product_name=product.name,
                    price=product.price,
                    stock=product.stock,
                    stock_value=product.price * product.stock,
                    last_updated=datetime.datetime.now(IST)
                ))
            return snapshots
        
        # If date filters are provided, calculate stock at that time
        print("🔄 Calculating historical stock with date filters")
        snapshots = []
        
        for product in products:
            print(f"🔍 Processing product: {product.name} (ID: {product.id})")
            
            # Convert date strings to datetime objects with better error handling
            date_from_dt = None
            date_to_dt = None
            
            if date_from:
                try:
                    # Try multiple date formats
                    if 'T' in date_from:
                        # ISO format with time
                        date_from_dt = datetime.datetime.fromisoformat(date_from.replace('Z', '+00:00'))
                    else:
                        # Simple date format (YYYY-MM-DD)
                        date_from_dt = datetime.datetime.strptime(date_from, '%Y-%m-%d')
                    print(f"   Date From parsed: {date_from_dt}")
                except ValueError as e:
                    print(f"❌ Error parsing date_from {date_from}: {e}")
                    # Try alternative format
                    try:
                        date_from_dt = datetime.datetime.fromisoformat(date_from)
                        print(f"   Date From parsed with alternative: {date_from_dt}")
                    except:
                        print(f"❌ Could not parse date_from {date_from}")
                        continue
            
            if date_to:
                try:
                    if 'T' in date_to:
                        # ISO format with time
                        date_to_dt = datetime.datetime.fromisoformat(date_to.replace('Z', '+00:00'))
                    else:
                        # Simple date format (YYYY-MM-DD)
                        date_to_dt = datetime.datetime.strptime(date_to, '%Y-%m-%d')
                        # Include the entire end date (up to 23:59:59)
                        date_to_dt = date_to_dt.replace(hour=23, minute=59, second=59)
                    print(f"   Date To parsed: {date_to_dt}")
                except ValueError as e:
                    print(f"❌ Error parsing date_to {date_to}: {e}")
                    # Try alternative format
                    try:
                        date_to_dt = datetime.datetime.fromisoformat(date_to)
                        print(f"   Date To parsed with alternative: {date_to_dt}")
                    except:
                        print(f"❌ Could not parse date_to {date_to}")
                        continue
            
            # If we couldn't parse dates but they were provided, skip historical calculation
            if (date_from and not date_from_dt) or (date_to and not date_to_dt):
                print("❌ Could not parse dates, using current stock")
                snapshots.append(ProductStockSnapshot(
                    product_id=product.id,
                    product_name=product.name,
                    price=product.price,
                    stock=product.stock,
                    stock_value=product.price * product.stock,
                    last_updated=datetime.datetime.now(IST)
                ))
                continue
            
            # Calculate opening stock (stock before the date range)
            opening_purchases_query = db.query(Purchase).filter(
                Purchase.product_id == product.id
            )
            opening_sales_query = db.query(Sale).filter(
                Sale.product_id == product.id
            )
            
            if date_from_dt:
                opening_purchases_query = opening_purchases_query.filter(Purchase.purchase_date < date_from_dt)
                opening_sales_query = opening_sales_query.filter(Sale.sale_date < date_from_dt)
            
            opening_purchases = opening_purchases_query.all()
            opening_sales = opening_sales_query.all()
            
            total_opening_purchases = sum(p.quantity for p in opening_purchases)
            total_opening_sales = sum(s.quantity for s in opening_sales)
            opening_stock = total_opening_purchases - total_opening_sales
            
            print(f"   Opening stock: {opening_stock} (Purchases: {total_opening_purchases}, Sales: {total_opening_sales})")
            
            # Calculate transactions within date range
            range_purchases_query = db.query(Purchase).filter(
                Purchase.product_id == product.id
            )
            range_sales_query = db.query(Sale).filter(
                Sale.product_id == product.id
            )
            
            if date_from_dt:
                range_purchases_query = range_purchases_query.filter(Purchase.purchase_date >= date_from_dt)
                range_sales_query = range_sales_query.filter(Sale.sale_date >= date_from_dt)
            
            if date_to_dt:
                range_purchases_query = range_purchases_query.filter(Purchase.purchase_date <= date_to_dt)
                range_sales_query = range_sales_query.filter(Sale.sale_date <= date_to_dt)
            
            range_purchases = range_purchases_query.all()
            range_sales = range_sales_query.all()
            
            total_range_purchases = sum(p.quantity for p in range_purchases)
            total_range_sales = sum(s.quantity for s in range_sales)
            
            print(f"   Range transactions - Purchases: {total_range_purchases}, Sales: {total_range_sales}")
            
            # Calculate stock at the end of date range
            stock_at_date = opening_stock + total_range_purchases - total_range_sales
            
            # Ensure stock doesn't go negative (shouldn't happen with proper data)
            stock_at_date = max(0, stock_at_date)
            
            # Use current price (or you could calculate average price for the period)
            current_price = product.price
            
            snapshots.append(ProductStockSnapshot(
                product_id=product.id,
                product_name=product.name,
                price=current_price,
                stock=stock_at_date,
                stock_value=current_price * stock_at_date,
                last_updated=datetime.datetime.now(IST)
            ))
            
            print(f"   Final stock at date: {stock_at_date}")
        
        print(f"✅ Generated {len(snapshots)} stock snapshots")
        return snapshots
        
    except Exception as e:
        print(f"❌ Error generating stock snapshot: {e}")
        import traceback
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=f"Error generating stock data: {str(e)}")


# --- SMS Endpoint ---
@app.post("/sms")
async def incoming_sms(request: Request):
    """Handles an incoming message from Twilio and sends a reply."""
    try:
        form_data: Dict[str, Any] = await request.form()
        incoming_message = form_data.get('Body', '').lower()
        from_number = form_data.get('From', '')

        print(f"Received message from {from_number}: '{incoming_message}'")

        resp = MessagingResponse()
        
        reply_message = None
        for product_name, price in PRODUCTS_DB.items():
            if product_name in incoming_message:
                reply_message = f"The price for {product_name.capitalize()} is ₹{price:.2f}."
                break
        
        if reply_message is None:
            reply_message = "Thank you for your message! Please visit our online store to place an order."

        resp.message(reply_message)
        return JSONResponse(content=str(resp), media_type="text/xml")

    except Exception as e:
        print(f"An error occurred: {e}")
        resp = MessagingResponse()
        resp.message("Sorry, something went wrong. Please try again later.")
        return JSONResponse(content=str(resp), media_type="text/xml")

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

if __name__ == "__main__":
    import uvicorn
    port = int(os.environ.get("PORT", 8000))
    uvicorn.run(app, host="0.0.0.0", port=port)