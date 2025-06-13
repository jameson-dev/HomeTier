# routes/devices.py (complete device API routes)

from flask import Blueprint, request, jsonify
from backend.database import get_db_connection, add_device
from datetime import datetime, timedelta

devices_bp = Blueprint('devices', __name__)

@devices_bp.route('/devices', methods=['GET'])
def get_devices():
    conn = get_db_connection()
    devices = conn.execute('SELECT * FROM devices ORDER BY last_seen DESC').fetchall()
    conn.close()
    return jsonify([dict(device) for device in devices])

@devices_bp.route('/devices/timeline', methods=['GET'])
def get_devices_timeline():
    """Get device discovery timeline data"""
    try:
        days = request.args.get('days', 7, type=int)
        days = max(1, min(days, 365))
        
        conn = get_db_connection()
        timeline_data = conn.execute('''
            SELECT 
                DATE(first_seen) as date,
                COUNT(*) as count
            FROM devices 
            WHERE datetime(first_seen) > datetime('now', '-{} days')
            GROUP BY DATE(first_seen)
            ORDER BY date ASC
        '''.format(days)).fetchall()
        conn.close()
        
        # Fill in missing dates with zero counts
        start_date = datetime.now() - timedelta(days=days)
        timeline = []
        data_dict = {row['date']: row['count'] for row in timeline_data}
        
        for i in range(days + 1):
            current_date = start_date + timedelta(days=i)
            date_str = current_date.strftime('%Y-%m-%d')
            timeline.append({
                'date': date_str,
                'count': data_dict.get(date_str, 0)
            })
        
        return jsonify({
            'status': 'success',
            'timeline': timeline,
            'period_days': days
        })
        
    except Exception as e:
        return jsonify({'status': 'error', 'message': str(e)}), 500

@devices_bp.route('/devices/<int:device_id>/ignore', methods=['POST'])
def ignore_device(device_id):
    try:
        conn = get_db_connection()
        conn.execute('UPDATE devices SET is_ignored = 1 WHERE id = ?', (device_id,))
        conn.commit()
        conn.close()
        return jsonify({'status': 'success'})
    except Exception as e:
        return jsonify({'status': 'error', 'message': str(e)}), 500

@devices_bp.route('/devices/<int:device_id>/unignore', methods=['POST'])
def unignore_device(device_id):
    try:
        conn = get_db_connection()
        device = conn.execute(
            'SELECT * FROM devices WHERE id = ? AND is_ignored = 1', 
            (device_id,)
        ).fetchone()
        
        if not device:
            conn.close()
            return jsonify({'status': 'error', 'message': 'Device not found or not currently ignored'}), 404
        
        conn.execute('UPDATE devices SET is_ignored = 0 WHERE id = ?', (device_id,))
        conn.commit()
        conn.close()
        return jsonify({'status': 'success', 'message': 'Device unignored successfully'})
    except Exception as e:
        return jsonify({'status': 'error', 'message': str(e)}), 500

@devices_bp.route('/devices/bulk/ignore', methods=['POST'])
def bulk_ignore_devices():
    try:
        data = request.get_json()
        device_ids = data.get('device_ids', [])
        
        if not device_ids:
            return jsonify({'status': 'error', 'message': 'No devices specified'}), 400
        
        conn = get_db_connection()
        placeholders = ','.join(['?' for _ in device_ids])
        conn.execute(f'UPDATE devices SET is_ignored = 1 WHERE id IN ({placeholders})', device_ids)
        affected_rows = conn.total_changes
        conn.commit()
        conn.close()
        
        return jsonify({
            'status': 'success', 
            'message': f'Successfully ignored {affected_rows} device(s)',
            'affected_count': affected_rows
        })
    except Exception as e:
        return jsonify({'status': 'error', 'message': str(e)}), 500

@devices_bp.route('/devices/bulk/unignore', methods=['POST'])
def bulk_unignore_devices():
    try:
        data = request.get_json()
        device_ids = data.get('device_ids', [])
        
        if not device_ids:
            return jsonify({'status': 'error', 'message': 'No devices specified'}), 400
        
        conn = get_db_connection()
        placeholders = ','.join(['?' for _ in device_ids])
        conn.execute(f'UPDATE devices SET is_ignored = 0 WHERE id IN ({placeholders})', device_ids)
        affected_rows = conn.total_changes
        conn.commit()
        conn.close()
        
        return jsonify({
            'status': 'success', 
            'message': f'Successfully unignored {affected_rows} device(s)',
            'affected_count': affected_rows
        })
    except Exception as e:
        return jsonify({'status': 'error', 'message': str(e)}), 500

@devices_bp.route('/devices/bulk/add-to-inventory', methods=['POST'])
def bulk_add_to_inventory():
    """Bulk add devices to inventory with common or individual settings"""
    try:
        data = request.get_json()
        device_ids = data.get('device_ids', [])
        mode = data.get('mode', 'common')
        
        if not device_ids:
            return jsonify({'status': 'error', 'message': 'No devices specified'}), 400
        
        conn = get_db_connection()
        
        # Get device information
        placeholders = ','.join(['?' for _ in device_ids])
        devices = conn.execute(f'''
            SELECT id, ip_address, hostname, mac_address, vendor 
            FROM devices 
            WHERE id IN ({placeholders})
        ''', device_ids).fetchall()
        
        # Check for devices already in active inventory
        existing_active = conn.execute(f'''
            SELECT device_id FROM inventory 
            WHERE device_id IN ({placeholders}) AND deleted_at IS NULL
        ''', device_ids).fetchall()
        
        # Check for devices in soft-deleted inventory
        existing_deleted = conn.execute(f'''
            SELECT device_id, id FROM inventory 
            WHERE device_id IN ({placeholders}) AND deleted_at IS NOT NULL
        ''', device_ids).fetchall()
        
        active_device_ids = set(row['device_id'] for row in existing_active)
        deleted_device_map = {row['device_id']: row['id'] for row in existing_deleted}
        
        added_count = 0
        restored_count = 0
        skipped_count = 0
        
        if mode == 'common':
            # Common mode - same settings for all devices
            common_data = data.get('common_data', {})
            use_auto_names = data.get('use_auto_names', True)
            
            for device in devices:
                if device['id'] in active_device_ids:
                    skipped_count += 1
                    continue
                
                # Determine device name
                if use_auto_names:
                    if device['hostname'] and device['hostname'] != 'Unknown':
                        device_name = device['hostname']
                    else:
                        device_name = f"Device {device['ip_address']}"
                else:
                    device_name = f"Device {device['ip_address']}"
                
                # Handle category
                category_id = common_data.get('category_id')
                category_name = common_data.get('category')
                
                # Check if this device was soft-deleted
                if device['id'] in deleted_device_map:
                    # Restore the soft-deleted item
                    conn.execute('''
                        UPDATE inventory 
                        SET name = ?, category_id = ?, category = ?, brand = ?, model = ?, purchase_date = ?, 
                            warranty_expiry = ?, store_vendor = ?, price = ?, serial_number = ?, 
                            notes = ?, deleted_at = NULL, updated_at = CURRENT_TIMESTAMP
                        WHERE id = ?
                    ''', (
                        device_name,
                        category_id,
                        category_name,
                        common_data.get('brand'),
                        common_data.get('model'),
                        common_data.get('purchase_date') or None,
                        common_data.get('warranty_expiry') or None,
                        common_data.get('store_vendor'),
                        float(common_data.get('price')) if common_data.get('price') else None,
                        common_data.get('serial_number'),
                        common_data.get('notes'),
                        deleted_device_map[device['id']]
                    ))
                    restored_count += 1
                else:
                    # Insert new inventory item
                    conn.execute('''
                        INSERT INTO inventory (device_id, name, category_id, category, brand, model, purchase_date, 
                                             warranty_expiry, store_vendor, price, serial_number, notes)
                        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    ''', (
                        device['id'],
                        device_name,
                        category_id,
                        category_name,
                        common_data.get('brand'),
                        common_data.get('model'),
                        common_data.get('purchase_date') or None,
                        common_data.get('warranty_expiry') or None,
                        common_data.get('store_vendor'),
                        float(common_data.get('price')) if common_data.get('price') else None,
                        common_data.get('serial_number'),
                        common_data.get('notes')
                    ))
                    added_count += 1
                
        else:
            # Individual mode - unique settings for each device
            device_data = data.get('device_data', {})
            
            for device in devices:
                if device['id'] in active_device_ids:
                    skipped_count += 1
                    continue
                
                device_id_str = str(device['id'])
                individual_data = device_data.get(device_id_str, {})
                
                # Use provided name or generate fallback
                device_name = individual_data.get('name') or f"Device {device['ip_address']}"
                
                # Handle category
                category_id = individual_data.get('category_id')
                category_name = individual_data.get('category')
                
                # Check if this device was soft-deleted
                if device['id'] in deleted_device_map:
                    # Restore the soft-deleted item
                    conn.execute('''
                        UPDATE inventory 
                        SET name = ?, category_id = ?, category = ?, brand = ?, model = ?, purchase_date = ?, 
                            warranty_expiry = ?, store_vendor = ?, price = ?, serial_number = ?, 
                            notes = ?, deleted_at = NULL, updated_at = CURRENT_TIMESTAMP
                        WHERE id = ?
                    ''', (
                        device_name,
                        category_id,
                        category_name,
                        individual_data.get('brand'),
                        individual_data.get('model'),
                        individual_data.get('purchase_date') or None,
                        individual_data.get('warranty_expiry') or None,
                        individual_data.get('store_vendor'),
                        float(individual_data.get('price')) if individual_data.get('price') else None,
                        individual_data.get('serial_number'),
                        individual_data.get('notes'),
                        deleted_device_map[device['id']]
                    ))
                    restored_count += 1
                else:
                    # Insert new inventory item
                    conn.execute('''
                        INSERT INTO inventory (device_id, name, category_id, category, brand, model, purchase_date, 
                                             warranty_expiry, store_vendor, price, serial_number, notes)
                        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    ''', (
                        device['id'],
                        device_name,
                        category_id,
                        category_name,
                        individual_data.get('brand'),
                        individual_data.get('model'),
                        individual_data.get('purchase_date') or None,
                        individual_data.get('warranty_expiry') or None,
                        individual_data.get('store_vendor'),
                        float(individual_data.get('price')) if individual_data.get('price') else None,
                        individual_data.get('serial_number'),
                        individual_data.get('notes')
                    ))
                    added_count += 1
        
        conn.commit()
        conn.close()
        
        # Build message based on what happened
        message_parts = []
        if added_count > 0:
            message_parts.append(f'Added {added_count} new device(s)')
        if restored_count > 0:
            message_parts.append(f'restored {restored_count} previously deleted device(s)')
        if skipped_count > 0:
            message_parts.append(f'{skipped_count} already in inventory')
            
        if message_parts:
            message = 'Successfully ' + ', '.join(message_parts) + ' to inventory'
        else:
            message = 'No devices were processed'
        
        return jsonify({
            'status': 'success',
            'message': message,
            'added_count': added_count,
            'restored_count': restored_count,
            'skipped_count': skipped_count
        })
        
    except Exception as e:
        return jsonify({'status': 'error', 'message': str(e)}), 500