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
    
    # Categories table - NEW
    conn.execute('''
        CREATE TABLE IF NOT EXISTS categories (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT UNIQUE NOT NULL,
            description TEXT,
            icon TEXT DEFAULT 'fas fa-desktop',
            color TEXT DEFAULT '#0d6efd',
            is_default BOOLEAN DEFAULT 0,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    ''')
    
    # Inventory table for managed equipment
    conn.execute('''
        CREATE TABLE IF NOT EXISTS inventory (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            device_id INTEGER UNIQUE,
            name TEXT NOT NULL,
            category_id INTEGER,
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
            FOREIGN KEY (device_id) REFERENCES devices (id),
            FOREIGN KEY (category_id) REFERENCES categories (id)
        )
    ''')
    
    # Add deleted_at column if it doesn't exist
    try:
        conn.execute('ALTER TABLE inventory ADD COLUMN deleted_at TIMESTAMP DEFAULT NULL')
        print("Migration: Added deleted_at column to inventory table")
    except Exception:
        pass
    
    # Add category_id column if it doesn't exist
    try:
        conn.execute('ALTER TABLE inventory ADD COLUMN category_id INTEGER REFERENCES categories(id)')
        print("Migration: Added category_id column to inventory table")
    except Exception:
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
    
    # Insert default categories
    default_categories = [
        ('Router', 'Network routers and gateways', 'fas fa-route', '#0d6efd', 1),
        ('Switch', 'Network switches and hubs', 'fas fa-network-wired', '#198754', 1),
        ('Access Point', 'WiFi access points and extenders', 'fas fa-wifi', '#fd7e14', 1),
        ('Smart Home', 'Smart home devices and IoT', 'fas fa-home', '#6f42c1', 1),
        ('Computer', 'Desktop computers, laptops, servers', 'fas fa-desktop', '#20c997', 1),
        ('Mobile', 'Phones, tablets, mobile devices', 'fas fa-mobile-alt', '#ffc107', 1),
        ('IoT', 'Internet of Things devices', 'fas fa-microchip', '#dc3545', 1),
        ('Appliance', 'Home appliances and equipment', 'fas fa-blender', '#6c757d', 1),
        ('Other', 'Other uncategorized devices', 'fas fa-question', '#adb5bd', 1)
    ]
    
    for name, description, icon, color, is_default in default_categories:
        try:
            conn.execute('''
                INSERT OR IGNORE INTO categories (name, description, icon, color, is_default)
                VALUES (?, ?, ?, ?, ?)
            ''', (name, description, icon, color, is_default))
        except Exception as e:
            print(f"Warning: Could not insert default category {name}: {e}")
    
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

def get_categories():
    """Get all categories ordered by default first, then alphabetically"""
    conn = get_db_connection()
    categories = conn.execute('''
        SELECT * FROM categories 
        ORDER BY is_default DESC, name ASC
    ''').fetchall()
    conn.close()
    return [dict(category) for category in categories]

def add_category(name, description=None, icon='fas fa-desktop', color='#0d6efd'):
    """Add a new custom category"""
    conn = get_db_connection()
    
    try:
        cursor = conn.execute('''
            INSERT INTO categories (name, description, icon, color, is_default)
            VALUES (?, ?, ?, ?, 0)
        ''', (name, description, icon, color))
        category_id = cursor.lastrowid
        conn.commit()
        conn.close()
        return category_id
    except sqlite3.IntegrityError:
        conn.close()
        raise ValueError(f"Category '{name}' already exists")

def update_category(category_id, name=None, description=None, icon=None, color=None):
    """Update an existing category"""
    conn = get_db_connection()
    
    # Check if category exists and is not default
    category = conn.execute(
        'SELECT * FROM categories WHERE id = ?', (category_id,)
    ).fetchone()
    
    if not category:
        conn.close()
        raise ValueError("Category not found")
    
    if category['is_default']:
        conn.close()
        raise ValueError("Cannot modify default categories")
    
    # Build update query dynamically
    update_fields = []
    values = []
    
    if name is not None:
        update_fields.append('name = ?')
        values.append(name)
    if description is not None:
        update_fields.append('description = ?')
        values.append(description)
    if icon is not None:
        update_fields.append('icon = ?')
        values.append(icon)
    if color is not None:
        update_fields.append('color = ?')
        values.append(color)
    
    if update_fields:
        update_fields.append('updated_at = CURRENT_TIMESTAMP')
        values.append(category_id)
        
        query = f"UPDATE categories SET {', '.join(update_fields)} WHERE id = ?"
        conn.execute(query, values)
        conn.commit()
    
    conn.close()

def delete_category(category_id):
    """Delete a custom category and update inventory items"""
    conn = get_db_connection()
    
    # Check if category exists and is not default
    category = conn.execute(
        'SELECT * FROM categories WHERE id = ?', (category_id,)
    ).fetchone()
    
    if not category:
        conn.close()
        raise ValueError("Category not found")
    
    if category['is_default']:
        conn.close()
        raise ValueError("Cannot delete default categories")
    
    # Get "Other" category ID as fallback
    other_category = conn.execute(
        'SELECT id FROM categories WHERE name = "Other" AND is_default = 1'
    ).fetchone()
    
    if other_category:
        # Update inventory items to use "Other" category
        conn.execute('''
            UPDATE inventory 
            SET category_id = ?, category = "Other", updated_at = CURRENT_TIMESTAMP
            WHERE category_id = ?
        ''', (other_category['id'], category_id))
    else:
        # Fallback: clear category references
        conn.execute('''
            UPDATE inventory 
            SET category_id = NULL, category = NULL, updated_at = CURRENT_TIMESTAMP
            WHERE category_id = ?
        ''', (category_id,))
    
    # Delete the category
    conn.execute('DELETE FROM categories WHERE id = ?', (category_id,))
    conn.commit()
    conn.close()