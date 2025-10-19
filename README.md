# Kirana Store Management API

A backend for managing a local Kirana store's products, sales, and purchases, including WhatsApp order simulation.

## Features

- 🚀 FastAPI backend with PostgreSQL
- 🔐 JWT Authentication with role-based permissions
- 📊 Sales and purchase ledger management
- 📈 Stock tracking and inventory reports
- 📱 WhatsApp order processing
- 📤 CSV/PDF export capabilities
- 💾 Database migrations included

## Tech Stack

- **Backend**: FastAPI (Python)
- **Database**: PostgreSQL
- **Authentication**: JWT + bcrypt
- **SMS**: Twilio integration
- **Deployment**: Railway (recommended)

## Deployment Options

### Railway (Recommended)
Railway provides excellent Python/PostgreSQL support with fast deployments.

1. Connect your GitHub repo to Railway
2. Add your PostgreSQL database (they provide it built-in)
3. Set the `DATABASE_URL` environment variable
4. Deploy!

### Local Development

```bash
# Install dependencies
pip install -r requirements.txt

# Set your DATABASE_URL in .env file
# Run the application
uvicorn main:app --host 0.0.0.0 --port 8000
```

## Environment Variables

```
DATABASE_URL=postgresql://user:password@host:port/database
SECRET_KEY_JWT=your-secret-key
```

## API Documentation

Once deployed, visit `/docs` for interactive API documentation.

## Update 10/19/2025
