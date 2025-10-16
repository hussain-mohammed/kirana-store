import os
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

# Database configuration
DATABASE_URL = os.getenv("DATABASE_URL")

# Function to be imported by handlers
def get_db_url():
    return DATABASE_URL

# Export for FastAPI
__all__ = ['get_db_url']
