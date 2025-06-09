from flask import Flask, render_template, request, jsonify
from backend.database import init_db, get_db_connection
from backend.scanner import NetworkScanner
from config import Config
import json
import csv
from datetime import datetime

app = Flask(__name__, 
           template_folder='frontend/templates',
           static_folder='frontend/static')
app.config.from_object(Config)

# Initialize database
init_db()

# Initialize network scanner
scanner = NetworkScanner()

@app.route('/')
def index():
    return render_template('index.html')

@app.route('/inventory')
def inventory():
    return render_template('inventory.html')

@app.route('/api/devices', methods=['GET'])
def get_devices():
    conn = get_db_connection()
    devices = conn.execute('SELECT * FROM devices ORDER BY last_seen DESC').fetchall()
    conn.close()
    
    return jsonify([dict(device) for device in devices])

@app.route('/api/scan', methods=['POST'])
def trigger_scan():
    try:
        devices = scanner.scan_network()
        return jsonify({
            'status': 'success',
            'devices_found': len(devices),
            'devices': devices
        })
    except Exception as e:
        return jsonify({'status': 'error', 'message': str(e)}), 500
    
@app.route('/api/inventory', methods=['GET'])
def get_inventory():
    conn = get_db_connection()
    inventory = conn.execute('''
        SELECT i.*, d.ip_address, d.mac_address 
        FROM inventory i
        LEFT JOIN devices d ON i.device_id = d.id
        ORDER BY i.created_at DESC
    ''').fetchall()
    conn.close()
    
    return jsonify([dict(item) for item in inventory])

@app.route('/api/inventory', methods=['POST'])
def add_inventory():
    try:
        data = request.form
        conn = get_db_connection()
        
        cursor = conn.execute('''
            INSERT INTO inventory (name, category, brand, model, purchase_date, 
                                 warranty_expiry, store_vendor, price, serial_number, notes)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        ''', (
            data.get('name'),
            data.get('category'),
            data.get('brand'),
            data.get('model'),
            data.get('purchase_date') or None,
            data.get('warranty_expiry') or None,
            data.get('store_vendor'),
            data.get('price') or None,
            data.get('serial_number'),
            data.get('notes')
        ))
        
        conn.commit()
        conn.close()
        
        return jsonify({'status': 'success', 'id': cursor.lastrowid})
        
    except Exception as e:
        return jsonify({'status': 'error', 'message': str(e)}), 500

@app.route('/api/devices/<int:device_id>/ignore', methods=['POST'])
def ignore_device(device_id):
    try:
        conn = get_db_connection()
        conn.execute('UPDATE devices SET is_ignored = 1 WHERE id = ?', (device_id,))
        conn.commit()
        conn.close()
        
        return jsonify({'status': 'success'})
        
    except Exception as e:
        return jsonify({'status': 'error', 'message': str(e)}), 500

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=app.config['5000'], debug=app.config['DEBUG'])