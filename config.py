import os
from datetime import timedelta

class Config:
    """Satın Alma Uygulaması Konfigürasyonu"""
    
    # Flask Secret Key
    SECRET_KEY = os.environ.get('SECRET_KEY') or 'purchasing-secret-key-2026-change-this'
    
    # Database
    SQLALCHEMY_DATABASE_URI = os.environ.get('DATABASE_URL') or \
        'sqlite:///purchasing.db'
    SQLALCHEMY_TRACK_MODIFICATIONS = False
    
    # Session
    PERMANENT_SESSION_LIFETIME = timedelta(hours=8)
    
    # Ana Stok Uygulaması API Bağlantısı
    # Local test: 'http://localhost:5000'
    # Canlı site: 'https://celmak.altikodtech.com.tr'
    STOCK_API_URL = os.environ.get('STOCK_API_URL') or 'https://celmak.altikodtech.com.trdtech.com.tr'
    STOCK_API_KEY = os.environ.get('STOCK_API_KEY') or 'sk_live_123456789'  # Ana stok .env ile aynı
    
    # Local Mode (True = Demo data, False = Real API)
    USE_LOCAL_MODE = os.environ.get('USE_LOCAL_MODE', 'False').lower() == 'true'
    
    # Pagination
    ITEMS_PER_PAGE = 20
    
    # File Upload
    UPLOAD_FOLDER = 'uploads'
    MAX_CONTENT_LENGTH = 16 * 1024 * 1024  # 16MB max
