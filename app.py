from flask import Flask, render_template, request, jsonify
from backend.database import init_db, get_db_connection
from backend.scanner import NetworkScanner
from config import Config
import json
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
        WHERE i.deleted_at IS NULL
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

@app.route('/api/inventory/<int:inventory_id>', methods=['DELETE'])
def delete_inventory_item(inventory_id):
    try:
        conn = get_db_connection()
        
        # Check if item exists and is not already deleted
        item = conn.execute(
            'SELECT * FROM inventory WHERE id = ? AND deleted_at IS NULL', 
            (inventory_id,)
        ).fetchone()
        
        if not item:
            conn.close()
            return jsonify({'status': 'error', 'message': 'Item not found or already deleted'}), 404
        
        # Soft delete - mark as deleted instead of removing
        conn.execute(
            'UPDATE inventory SET deleted_at = CURRENT_TIMESTAMP WHERE id = ?', 
            (inventory_id,)
        )
        conn.commit()
        conn.close()
        
        return jsonify({'status': 'success', 'message': 'Item deleted successfully'})
        
    except Exception as e:
        return jsonify({'status': 'error', 'message': str(e)}), 500

@app.route('/api/inventory/export/<format>', methods=['GET'])
def export_inventory(format):
    try:
        conn = get_db_connection()
        inventory = conn.execute('''
            SELECT i.*, d.ip_address, d.mac_address, d.hostname
            FROM inventory i
            LEFT JOIN devices d ON i.device_id = d.id
            WHERE i.deleted_at IS NULL
            ORDER BY i.created_at DESC
        ''').fetchall()
        conn.close()
        
        if format.lower() == 'csv':
            return export_to_csv(inventory)
        elif format.lower() == 'json':
            return export_to_json(inventory)
        else:
            return jsonify({'status': 'error', 'message': 'Invalid format'}), 400
            
    except Exception as e:
        return jsonify({'status': 'error', 'message': str(e)}), 500

def export_to_csv(inventory):
    import csv
    import io
    from flask import make_response
    
    output = io.StringIO()
    writer = csv.writer(output)
    
    # Write header
    writer.writerow([
        'ID', 'Name', 'Category', 'Brand', 'Model', 'Purchase Date', 
        'Warranty Expiry', 'Store/Vendor', 'Price', 'Serial Number', 
        'IP Address', 'MAC Address', 'Hostname', 'Notes', 'Created At'
    ])
    
    # Write data
    for item in inventory:
        writer.writerow([
            item['id'],
            item['name'],
            item['category'] or '',
            item['brand'] or '',
            item['model'] or '',
            item['purchase_date'] or '',
            item['warranty_expiry'] or '',
            item['store_vendor'] or '',
            item['price'] or '',
            item['serial_number'] or '',
            item['ip_address'] or '',
            item['mac_address'] or '',
            item['hostname'] or '',
            item['notes'] or '',
            item['created_at']
        ])
    
    output.seek(0)
    
    response = make_response(output.getvalue())
    response.headers['Content-Type'] = 'text/csv'
    response.headers['Content-Disposition'] = f'attachment; filename=inventory_export_{datetime.now().strftime("%Y%m%d_%H%M%S")}.csv'
    
    return response

def export_to_json(inventory):
    from flask import make_response
    
    # Convert to list of dictionaries
    data = []
    for item in inventory:
        data.append({
            'id': item['id'],
            'name': item['name'],
            'category': item['category'],
            'brand': item['brand'],
            'model': item['model'],
            'purchase_date': item['purchase_date'],
            'warranty_expiry': item['warranty_expiry'],
            'store_vendor': item['store_vendor'],
            'price': item['price'],
            'serial_number': item['serial_number'],
            'ip_address': item['ip_address'],
            'mac_address': item['mac_address'],
            'hostname': item['hostname'],
            'notes': item['notes'],
            'created_at': item['created_at'],
            'updated_at': item['updated_at']
        })
    
    export_data = {
        'export_date': datetime.now().isoformat(),
        'total_items': len(data),
        'inventory': data
    }
    
    response = make_response(json.dumps(export_data, indent=2))
    response.headers['Content-Type'] = 'application/json'
    response.headers['Content-Disposition'] = f'attachment; filename=inventory_export_{datetime.now().strftime("%Y%m%d_%H%M%S")}.json'
    
    return response

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

@app.route('/scanner')
def scanner():
    return render_template('scanner.html')

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=app.config['PORT'], debug=app.config['DEBUG'])