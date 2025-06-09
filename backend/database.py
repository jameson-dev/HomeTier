import sqlite3
from pathlib import Path
from config import Config
from datetime import datetime

def get_db_connection():
    """Get database connection"""
    conn = sqlite3.connect(Config.DATABASE_PATH)
    conn.row_factory = sqlite3.Row
    return conn

def init_db():
    """Initialize database with required tables"""
    conn = get_db_connection()
    
    # Devices table
    conn.execute('''
        CREATE TABLE IF NOT EXISTS devices (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            mac_address TEXT UNIQUE NOT NULL,
            ip_address TEXT,
            hostname TEXT,
            vendor TEXT,
            device_type TEXT,
            first_seen TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            last_seen TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            is_monitored BOOLEAN DEFAULT 1,
            is_ignored BOOLEAN DEFAULT 0,
            notes TEXT
        )
    ''')
    
    # Inventory table for managed equipment
    conn.execute('''
        CREATE TABLE IF NOT EXISTS inventory (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            device_id INTEGER,
            name TEXT NOT NULL,
            category TEXT,
            brand TEXT,
            model TEXT,
            purchase_date DATE,
            warranty_expiry DATE,
            store_vendor TEXT,
            price DECIMAL(10,2),
            serial_number TEXT,
            notes TEXT,
            photo_path TEXT,
            receipt_path TEXT,
            deleted_at TIMESTAMP DEFAULT NULL,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (device_id) REFERENCES devices (id)
        )
    ''')
    
    try:
        conn.execute('ALTER TABLE inventory ADD COLUMN deleted_at TIMESTAMP DEFAULT NULL')
        print("Migration: Added deleted_at column to inventory table")
    except Exception as e:
        # Column already exists or table doesn't exist yet - ignore error
        pass
    
    # Device relationships table
    conn.execute('''
        CREATE TABLE IF NOT EXISTS device_relationships (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            parent_device_id INTEGER,
            child_device_id INTEGER,
            relationship_type TEXT DEFAULT 'connected_to',
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (parent_device_id) REFERENCES devices (id),
            FOREIGN KEY (child_device_id) REFERENCES devices (id)
        )
    ''')
    
    # Notification settings table
    conn.execute('''
        CREATE TABLE IF NOT EXISTS notification_settings (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            rule_name TEXT NOT NULL,
            filter_type TEXT NOT NULL, -- 'vendor', 'mac_prefix', 'ip_range'
            filter_value TEXT NOT NULL,
            action TEXT NOT NULL, -- 'alert', 'ignore', 'auto_add'
            is_active BOOLEAN DEFAULT 1,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    ''')
    
    conn.commit()
    conn.close()
    print("Database initialized successfully")

def add_device(mac_address, ip_address=None, hostname=None, vendor=None):
    """Add or update device in database"""
    conn = get_db_connection()
    
    # Check if device exists
    existing = conn.execute(
        'SELECT id FROM devices WHERE mac_address = ?', 
        (mac_address,)
    ).fetchone()
    
    if existing:
        # Update existing device
        conn.execute('''
            UPDATE devices 
            SET ip_address = ?, hostname = ?, vendor = ?, last_seen = CURRENT_TIMESTAMP
            WHERE mac_address = ?
        ''', (ip_address, hostname, vendor, mac_address))
        device_id = existing['id']
    else:
        # Insert new device
        cursor = conn.execute('''
            INSERT INTO devices (mac_address, ip_address, hostname, vendor)
            VALUES (?, ?, ?, ?)
        ''', (mac_address, ip_address, hostname, vendor))
        device_id = cursor.lastrowid
    
    conn.commit()
    conn.close()
    return device_id

def get_new_devices():
    """Get devices discovered in the last scan that aren't in inventory"""
    conn = get_db_connection()
    devices = conn.execute('''
        SELECT d.* FROM devices d
        LEFT JOIN inventory i ON d.id = i.device_id
        WHERE i.device_id IS NULL 
        AND d.is_ignored = 0
        AND datetime(d.first_seen) > datetime('now', '-1 hour')
        ORDER BY d.first_seen DESC
    ''').fetchall()
    conn.close()
    return [dict(device) for device in devices]