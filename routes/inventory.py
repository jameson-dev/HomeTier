from flask import Blueprint, request, jsonify
from backend.database import get_db_connection
from services.export_service import ExportService

inventory_bp = Blueprint('inventory', __name__)

@inventory_bp.route('/inventory', methods=['GET'])
def get_inventory():
    """Get all inventory items with device and category information"""
    conn = get_db_connection()
    inventory = conn.execute('''
        SELECT 
            i.*, 
            d.ip_address, 
            d.mac_address,
            d.hostname,
            c.name as category_name,
            c.icon as category_icon,
            c.color as category_color
        FROM inventory i
        LEFT JOIN devices d ON i.device_id = d.id
        LEFT JOIN categories c ON i.category_id = c.id
        WHERE i.deleted_at IS NULL
        ORDER BY i.created_at DESC
    ''').fetchall()
    conn.close()
    
    return jsonify([dict(item) for item in inventory])

@inventory_bp.route('/inventory', methods=['POST'])
def add_inventory():
    """Add new item to inventory"""
    try:
        data = request.form
        conn = get_db_connection()
        
        # Handle category - could be category_id or legacy category text
        category_id = data.get('category_id')
        category_text = data.get('category')
        
        # If category_id is provided, use it; otherwise try to find category by name
        if category_id and category_id.isdigit():
            category_id = int(category_id)
            # Verify category exists
            category = conn.execute('SELECT name FROM categories WHERE id = ?', (category_id,)).fetchone()
            category_text = category['name'] if category else None
        elif category_text:
            # Try to find category by name
            category = conn.execute('SELECT id FROM categories WHERE name = ?', (category_text,)).fetchone()
            category_id = category['id'] if category else None
        else:
            category_id = None
            category_text = None
        
        # Check if device is already in inventory (only if device_id provided)
        if data.get('device_id'):
            # First check for active (non-deleted) inventory items
            existing_active = conn.execute('''
                SELECT id FROM inventory 
                WHERE device_id = ? AND deleted_at IS NULL
            ''', (data.get('device_id'),)).fetchone()
            
            if existing_active:
                conn.close()
                return jsonify({
                    'status': 'error', 
                    'message': 'This device is already in your inventory'
                }), 400
            
            # Check for soft-deleted inventory items
            existing_deleted = conn.execute('''
                SELECT id FROM inventory 
                WHERE device_id = ? AND deleted_at IS NOT NULL
            ''', (data.get('device_id'),)).fetchone()
            
            if existing_deleted:
                # Restore the soft-deleted item with new data
                conn.execute('''
                    UPDATE inventory 
                    SET name = ?, category_id = ?, category = ?, brand = ?, model = ?, purchase_date = ?, 
                        warranty_expiry = ?, store_vendor = ?, price = ?, serial_number = ?, 
                        notes = ?, deleted_at = NULL, updated_at = CURRENT_TIMESTAMP
                    WHERE id = ?
                ''', (
                    data.get('name'),
                    category_id,
                    category_text,
                    data.get('brand'),
                    data.get('model'),
                    data.get('purchase_date') or None,
                    data.get('warranty_expiry') or None,
                    data.get('store_vendor'),
                    data.get('price') or None,
                    data.get('serial_number'),
                    data.get('notes'),
                    existing_deleted['id']
                ))
                
                conn.commit()
                conn.close()
                
                return jsonify({'status': 'success', 'id': existing_deleted['id'], 'action': 'restored'})
        
        # Create new inventory item if no existing record found
        cursor = conn.execute('''
            INSERT INTO inventory (device_id, name, category_id, category, brand, model, purchase_date, 
                                 warranty_expiry, store_vendor, price, serial_number, notes)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        ''', (
            data.get('device_id') or None,
            data.get('name'),
            category_id,
            category_text,
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
        
        return jsonify({'status': 'success', 'id': cursor.lastrowid, 'action': 'created'})
        
    except Exception as e:
        return jsonify({'status': 'error', 'message': str(e)}), 500

@inventory_bp.route('/inventory/<int:inventory_id>', methods=['PUT'])
def update_inventory_item(inventory_id):
    """Update an existing inventory item"""
    try:
        data = request.get_json()
        conn = get_db_connection()
        
        # Check if item exists and is not deleted
        item = conn.execute(
            'SELECT * FROM inventory WHERE id = ? AND deleted_at IS NULL', 
            (inventory_id,)
        ).fetchone()
        
        if not item:
            conn.close()
            return jsonify({'status': 'error', 'message': 'Item not found or already deleted'}), 404
        
        # Handle category
        category_id = data.get('category_id')
        category_text = data.get('category')
        
        if category_id:
            category = conn.execute('SELECT name FROM categories WHERE id = ?', (category_id,)).fetchone()
            category_text = category['name'] if category else None
        elif category_text:
            category = conn.execute('SELECT id FROM categories WHERE name = ?', (category_text,)).fetchone()
            category_id = category['id'] if category else None
        
        # Update the item
        conn.execute('''
            UPDATE inventory 
            SET name = ?, category_id = ?, category = ?, brand = ?, model = ?, purchase_date = ?, 
                warranty_expiry = ?, store_vendor = ?, price = ?, serial_number = ?, 
                notes = ?, updated_at = CURRENT_TIMESTAMP
            WHERE id = ?
        ''', (
            data.get('name'),
            category_id,
            category_text,
            data.get('brand'),
            data.get('model'),
            data.get('purchase_date'),
            data.get('warranty_expiry'),
            data.get('store_vendor'),
            data.get('price'),
            data.get('serial_number'),
            data.get('notes'),
            inventory_id
        ))
        
        conn.commit()
        conn.close()
        
        return jsonify({'status': 'success', 'message': 'Item updated successfully'})
        
    except Exception as e:
        return jsonify({'status': 'error', 'message': str(e)}), 500

@inventory_bp.route('/inventory/<int:inventory_id>', methods=['DELETE'])
def delete_inventory_item(inventory_id):
    """Soft delete an inventory item"""
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

@inventory_bp.route('/inventory/<int:inventory_id>/restore', methods=['POST'])
def restore_inventory_item(inventory_id):
    """Restore a soft-deleted inventory item"""
    try:
        conn = get_db_connection()
        
        # Check if item exists and is deleted
        item = conn.execute(
            'SELECT * FROM inventory WHERE id = ? AND deleted_at IS NOT NULL', 
            (inventory_id,)
        ).fetchone()
        
        if not item:
            conn.close()
            return jsonify({'status': 'error', 'message': 'Item not found or not deleted'}), 404
        
        # Restore the item
        conn.execute(
            'UPDATE inventory SET deleted_at = NULL, updated_at = CURRENT_TIMESTAMP WHERE id = ?', 
            (inventory_id,)
        )
        conn.commit()
        conn.close()
        
        return jsonify({'status': 'success', 'message': 'Item restored successfully'})
        
    except Exception as e:
        return jsonify({'status': 'error', 'message': str(e)}), 500

@inventory_bp.route('/inventory/bulk/delete', methods=['POST'])
def bulk_delete_inventory():
    """Bulk soft delete inventory items"""
    try:
        data = request.get_json()
        item_ids = data.get('item_ids', [])
        
        if not item_ids:
            return jsonify({'status': 'error', 'message': 'No items specified'}), 400
        
        conn = get_db_connection()
        
        # Soft delete all specified items
        placeholders = ','.join(['?' for _ in item_ids])
        conn.execute(f'''
            UPDATE inventory 
            SET deleted_at = CURRENT_TIMESTAMP 
            WHERE id IN ({placeholders}) AND deleted_at IS NULL
        ''', item_ids)
        
        affected_rows = conn.total_changes
        conn.commit()
        conn.close()
        
        return jsonify({
            'status': 'success',
            'message': f'Successfully deleted {affected_rows} item(s)',
            'affected_count': affected_rows
        })
        
    except Exception as e:
        return jsonify({'status': 'error', 'message': str(e)}), 500

@inventory_bp.route('/inventory/export/<format_type>', methods=['GET'])
def export_inventory(format_type):
    """Export inventory data in various formats"""
    try:
        export_service = ExportService()
        
        if format_type.lower() == 'csv':
            return export_service.export_inventory_csv()
        elif format_type.lower() == 'json':
            return export_service.export_inventory_json()
        elif format_type.lower() == 'report':
            return export_service.export_combined_report()
        else:
            return jsonify({'status': 'error', 'message': 'Invalid export format'}), 400
            
    except Exception as e:
        return jsonify({'status': 'error', 'message': str(e)}), 500

@inventory_bp.route('/inventory/stats', methods=['GET'])
def get_inventory_stats():
    """Get inventory statistics"""
    try:
        conn = get_db_connection()
        
        # Basic counts
        total_items = conn.execute('''
            SELECT COUNT(*) as count FROM inventory WHERE deleted_at IS NULL
        ''').fetchone()['count']
        
        # Category breakdown
        category_stats = conn.execute('''
            SELECT 
                COALESCE(c.name, i.category, 'Uncategorized') as category,
                COUNT(*) as count,
                COALESCE(c.color, '#6c757d') as color,
                COALESCE(c.icon, 'fas fa-question') as icon
            FROM inventory i
            LEFT JOIN categories c ON i.category_id = c.id
            WHERE i.deleted_at IS NULL 
            GROUP BY COALESCE(c.name, i.category, 'Uncategorized')
            ORDER BY count DESC
        ''').fetchall()
        
        # Warranty status
        warranty_stats = conn.execute('''
            SELECT 
                CASE 
                    WHEN warranty_expiry IS NULL THEN 'unknown'
                    WHEN DATE(warranty_expiry) < DATE('now') THEN 'expired'
                    WHEN DATE(warranty_expiry) <= DATE('now', '+30 days') THEN 'expiring'
                    ELSE 'active'
                END as status,
                COUNT(*) as count
            FROM inventory
            WHERE deleted_at IS NULL
            GROUP BY status
        ''').fetchall()
        
        # Value statistics
        value_stats = conn.execute('''
            SELECT 
                COUNT(CASE WHEN price IS NOT NULL AND CAST(price as REAL) > 0 THEN 1 END) as items_with_price,
                COALESCE(SUM(CAST(price as REAL)), 0) as total_value,
                COALESCE(AVG(CAST(price as REAL)), 0) as average_value,
                COALESCE(MAX(CAST(price as REAL)), 0) as highest_value
            FROM inventory 
            WHERE deleted_at IS NULL
        ''').fetchone()
        
        # Recent additions
        recent_additions = conn.execute('''
            SELECT COUNT(*) as count
            FROM inventory
            WHERE deleted_at IS NULL 
            AND datetime(created_at) > datetime('now', '-30 days')
        ''').fetchone()['count']
        
        conn.close()
        
        return jsonify({
            'status': 'success',
            'stats': {
                'total_items': total_items,
                'recent_additions_30d': recent_additions,
                'category_breakdown': [dict(row) for row in category_stats],
                'warranty_status': [dict(row) for row in warranty_stats],
                'value_stats': {
                    'items_with_price': value_stats['items_with_price'],
                    'total_value': round(value_stats['total_value'], 2),
                    'average_value': round(value_stats['average_value'], 2),
                    'highest_value': round(value_stats['highest_value'], 2)
                }
            }
        })
        
    except Exception as e:
        return jsonify({'status': 'error', 'message': str(e)}), 500

@inventory_bp.route('/inventory/search', methods=['GET'])
def search_inventory():
    """Search inventory items"""
    try:
        query = request.args.get('q', '').strip()
        category = request.args.get('category', '').strip()
        warranty_status = request.args.get('warranty_status', '').strip()
        
        if not query and not category and not warranty_status:
            return jsonify({'status': 'error', 'message': 'No search criteria provided'}), 400
        
        conn = get_db_connection()
        
        # Build WHERE clause
        where_conditions = ['i.deleted_at IS NULL']
        params = []
        
        if query:
            where_conditions.append('''
                (i.name LIKE ? OR i.brand LIKE ? OR i.model LIKE ? OR 
                 i.serial_number LIKE ? OR i.notes LIKE ? OR d.hostname LIKE ?)
            ''')
            like_query = f'%{query}%'
            params.extend([like_query] * 6)
        
        if category:
            where_conditions.append('(c.name = ? OR i.category = ?)')
            params.extend([category, category])
        
        if warranty_status:
            if warranty_status == 'expired':
                where_conditions.append('i.warranty_expiry < DATE("now")')
            elif warranty_status == 'expiring':
                where_conditions.append('i.warranty_expiry BETWEEN DATE("now") AND DATE("now", "+30 days")')
            elif warranty_status == 'active':
                where_conditions.append('i.warranty_expiry > DATE("now", "+30 days")')
            elif warranty_status == 'unknown':
                where_conditions.append('i.warranty_expiry IS NULL')
        
        where_clause = ' AND '.join(where_conditions)
        
        results = conn.execute(f'''
            SELECT 
                i.*, 
                d.ip_address, 
                d.mac_address,
                d.hostname,
                c.name as category_name,
                c.icon as category_icon,
                c.color as category_color
            FROM inventory i
            LEFT JOIN devices d ON i.device_id = d.id
            LEFT JOIN categories c ON i.category_id = c.id
            WHERE {where_clause}
            ORDER BY i.updated_at DESC
        ''', params).fetchall()
        
        conn.close()
        
        return jsonify({
            'status': 'success',
            'results': [dict(item) for item in results],
            'count': len(results)
        })
        
    except Exception as e:
        return jsonify({'status': 'error', 'message': str(e)}), 500