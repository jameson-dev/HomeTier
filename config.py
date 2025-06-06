import os
from pathlib import Path

class Config:
    # Database
    DATABASE_PATH = os.getenv('DATABASE_PATH', 'data/inventory.db')
    
    # Flask
    SECRET_KEY = os.getenv('SECRET_KEY', 'your-secret-key-change-this')
    DEBUG = os.getenv('FLASK_DEBUG', 'False').lower() == 'true'
    
    # Network scanning
    SCAN_INTERVAL = int(os.getenv('SCAN_INTERVAL', 300))  # 5 minutes
    NETWORK_RANGE = os.getenv('NETWORK_RANGE', '192.168.1.0/24')
    
    # Data directory
    DATA_DIR = Path('data')
    DATA_DIR.mkdir(exist_ok=True)