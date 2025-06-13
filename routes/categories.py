# routes/categories.py

from flask import Blueprint, request, jsonify
from backend.database import get_categories, add_category, update_category, delete_category, get_db_connection

categories_bp = Blueprint('categories', __name__)

@categories_bp.route('/categories', methods=['GET'])
def get_categories_api():
    """Get all categories"""
    try:
        categories = get_categories()
        return jsonify({'status': 'success', 'categories': categories})
    except Exception as e:
        return jsonify({'status': 'error', 'message': str(e)}), 500

@categories_bp.route('/categories', methods=['POST'])
def add_category_api():
    """Add a new category"""
    try:
        data = request.get_json()
        
        if not data or not data.get('name'):
            return jsonify({'status': 'error', 'message': 'Category name is required'}), 400
        
        name = data['name'].strip()
        description = data.get('description', '').strip() or None
        icon = data.get('icon', 'fas fa-desktop')
        color = data.get('color', '#0d6efd')
        
        # Validation
        if len(name) < 2:
            return jsonify({'status': 'error', 'message': 'Category name must be at least 2 characters'}), 400
        
        if len(name) > 50:
            return jsonify({'status': 'error', 'message': 'Category name must be less than 50 characters'}), 400
        
        # Check for duplicate names
        conn = get_db_connection()
        existing = conn.execute('SELECT id FROM categories WHERE LOWER(name) = LOWER(?)', (name,)).fetchone()
        conn.close()
        
        if existing:
            return jsonify({'status': 'error', 'message': 'A category with this name already exists'}), 400
        
        category_id = add_category(name, description, icon, color)
        
        return jsonify({
            'status': 'success', 
            'message': 'Category created successfully',
            'category_id': category_id
        })
        
    except ValueError as e:
        return jsonify({'status': 'error', 'message': str(e)}), 400
    except Exception as e:
        return jsonify({'status': 'error', 'message': str(e)}), 500

@categories_bp.route('/categories/<int:category_id>', methods=['GET'])
def get_category_api(category_id):
    """Get a specific category by ID"""
    try:
        conn = get_db_connection()
        category = conn.execute('SELECT * FROM categories WHERE id = ?', (category_id,)).fetchone()
        conn.close()
        
        if not category:
            return jsonify({'status': 'error', 'message': 'Category not found'}), 404
        
        return jsonify({
            'status': 'success',
            'category': dict(category)
        })
        
    except Exception as e:
        return jsonify({'status': 'error', 'message': str(e)}), 500

@categories_bp.route('/categories/<int:category_id>', methods=['PUT'])
def update_category_api(category_id):
    """Update an existing category"""
    try:
        data = request.get_json()
        
        if not data:
            return jsonify({'status': 'error', 'message': 'No data provided'}), 400
        
        # Validate name if provided
        if 'name' in data:
            name = data['name'].strip()
            if len(name) < 2:
                return jsonify({'status': 'error', 'message': 'Category name must be at least 2 characters'}), 400
            if len(name) > 50:
                return jsonify({'status': 'error', 'message': 'Category name must be less than 50 characters'}), 400
            data['name'] = name
            
            # Check for duplicate names (excluding current category)
            conn = get_db_connection()
            existing = conn.execute(
                'SELECT id FROM categories WHERE LOWER(name) = LOWER(?) AND id != ?', 
                (name, category_id)
            ).fetchone()
            conn.close()
            
            if existing:
                return jsonify({'status': 'error', 'message': 'A category with this name already exists'}), 400
        
        # Validate description if provided
        if 'description' in data:
            data['description'] = data['description'].strip() or None
        
        update_category(
            category_id,
            name=data.get('name'),
            description=data.get('description'),
            icon=data.get('icon'),
            color=data.get('color')
        )
        
        return jsonify({
            'status': 'success', 
            'message': 'Category updated successfully'
        })
        
    except ValueError as e:
        return jsonify({'status': 'error', 'message': str(e)}), 400
    except Exception as e:
        return jsonify({'status': 'error', 'message': str(e)}), 500

@categories_bp.route('/categories/<int:category_id>', methods=['DELETE'])
def delete_category_api(category_id):
    """Delete a category"""
    try:
        delete_category(category_id)
        
        return jsonify({
            'status': 'success', 
            'message': 'Category deleted successfully'
        })
        
    except ValueError as e:
        return jsonify({'status': 'error', 'message': str(e)}), 400
    except Exception as e:
        return jsonify({'status': 'error', 'message': str(e)}), 500

@categories_bp.route('/categories/<int:category_id>/items', methods=['GET'])
def get_category_items(category_id):
    """Get all inventory items in a specific category"""
    try:
        conn = get_db_connection()
        
        # Check if category exists
        category = conn.execute('SELECT * FROM categories WHERE id = ?', (category_id,)).fetchone()
        if not category:
            conn.close()
            return jsonify({'status': 'error', 'message': 'Category not found'}), 404
        
        # Get items in this category
        items = conn.execute('''
            SELECT i.*, d.ip_address, d.mac_address, d.hostname
            FROM inventory i
            LEFT JOIN devices d ON i.device_id = d.id
            WHERE i.category_id = ? AND i.deleted_at IS NULL
            ORDER BY i.updated_at DESC
        ''', (category_id,)).fetchall()
        
        conn.close()
        
        return jsonify({
            'status': 'success',
            'category': dict(category),
            'items': [dict(item) for item in items],
            'count': len(items)
        })
        
    except Exception as e:
        return jsonify({'status': 'error', 'message': str(e)}), 500

@categories_bp.route('/categories/<int:category_id>/stats', methods=['GET'])
def get_category_stats(category_id):
    """Get statistics for a specific category"""
    try:
        conn = get_db_connection()
        
        # Check if category exists
        category = conn.execute('SELECT * FROM categories WHERE id = ?', (category_id,)).fetchone()
        if not category:
            conn.close()
            return jsonify({'status': 'error', 'message': 'Category not found'}), 404
        
        # Get category statistics
        stats = conn.execute('''
            SELECT 
                COUNT(*) as total_items,
                COUNT(CASE WHEN price IS NOT NULL AND CAST(price as REAL) > 0 THEN 1 END) as items_with_price,
                COALESCE(SUM(CAST(price as REAL)), 0) as total_value,
                COALESCE(AVG(CAST(price as REAL)), 0) as average_value,
                COUNT(CASE WHEN warranty_expiry IS NOT NULL AND DATE(warranty_expiry) > DATE('now') THEN 1 END) as items_under_warranty,
                COUNT(CASE WHEN warranty_expiry IS NOT NULL AND DATE(warranty_expiry) < DATE('now') THEN 1 END) as items_warranty_expired,
                COUNT(CASE WHEN device_id IS NOT NULL THEN 1 END) as networked_items
            FROM inventory 
            WHERE category_id = ? AND deleted_at IS NULL
        ''', (category_id,)).fetchone()
        
        # Recent additions in this category
        recent_items = conn.execute('''
            SELECT COUNT(*) as count
            FROM inventory
            WHERE category_id = ? AND deleted_at IS NULL 
            AND datetime(created_at) > datetime('now', '-30 days')
        ''', (category_id,)).fetchone()
        
        conn.close()
        
        return jsonify({
            'status': 'success',
            'category': dict(category),
            'stats': {
                'total_items': stats['total_items'],
                'items_with_price': stats['items_with_price'],
                'total_value': round(stats['total_value'], 2),
                'average_value': round(stats['average_value'], 2),
                'items_under_warranty': stats['items_under_warranty'],
                'items_warranty_expired': stats['items_warranty_expired'],
                'networked_items': stats['networked_items'],
                'recent_additions_30d': recent_items['count']
            }
        })
        
    except Exception as e:
        return jsonify({'status': 'error', 'message': str(e)}), 500

@categories_bp.route('/categories/stats', methods=['GET'])
def get_all_categories_stats():
    """Get statistics for all categories"""
    try:
        conn = get_db_connection()
        
        # Get stats for all categories including usage counts
        category_stats = conn.execute('''
            SELECT 
                c.*,
                COALESCE(item_counts.item_count, 0) as item_count,
                COALESCE(item_counts.total_value, 0) as total_value
            FROM categories c
            LEFT JOIN (
                SELECT 
                    category_id,
                    COUNT(*) as item_count,
                    COALESCE(SUM(CAST(price as REAL)), 0) as total_value
                FROM inventory 
                WHERE deleted_at IS NULL 
                GROUP BY category_id
            ) item_counts ON c.id = item_counts.category_id
            ORDER BY item_counts.item_count DESC NULLS LAST, c.name ASC
        ''').fetchall()
        
        # Get total inventory count for percentages
        total_items = conn.execute('''
            SELECT COUNT(*) as count FROM inventory WHERE deleted_at IS NULL
        ''').fetchone()['count']
        
        conn.close()
        
        # Calculate percentages and format response
        stats = []
        for category in category_stats:
            cat_dict = dict(category)
            cat_dict['percentage'] = round((cat_dict['item_count'] / total_items * 100) if total_items > 0 else 0, 1)
            cat_dict['total_value'] = round(cat_dict['total_value'], 2)
            stats.append(cat_dict)
        
        return jsonify({
            'status': 'success',
            'categories': stats,
            'summary': {
                'total_categories': len(stats),
                'categories_in_use': len([c for c in stats if c['item_count'] > 0]),
                'total_items': total_items
            }
        })
        
    except Exception as e:
        return jsonify({'status': 'error', 'message': str(e)}), 500

@categories_bp.route('/categories/unused', methods=['GET'])
def get_unused_categories():
    """Get categories that have no inventory items"""
    try:
        conn = get_db_connection()
        
        unused_categories = conn.execute('''
            SELECT c.*
            FROM categories c
            LEFT JOIN inventory i ON c.id = i.category_id AND i.deleted_at IS NULL
            WHERE i.category_id IS NULL AND c.is_default = 0
            ORDER BY c.created_at DESC
        ''').fetchall()
        
        conn.close()
        
        return jsonify({
            'status': 'success',
            'categories': [dict(cat) for cat in unused_categories],
            'count': len(unused_categories)
        })
        
    except Exception as e:
        return jsonify({'status': 'error', 'message': str(e)}), 500

@categories_bp.route('/categories/bulk/delete', methods=['POST'])
def bulk_delete_categories():
    """Bulk delete unused custom categories"""
    try:
        data = request.get_json()
        category_ids = data.get('category_ids', [])
        
        if not category_ids:
            return jsonify({'status': 'error', 'message': 'No categories specified'}), 400
        
        conn = get_db_connection()
        
        # Only allow deletion of custom (non-default) categories that have no items
        placeholders = ','.join(['?' for _ in category_ids])
        deletable_categories = conn.execute(f'''
            SELECT c.id, c.name
            FROM categories c
            LEFT JOIN inventory i ON c.id = i.category_id AND i.deleted_at IS NULL
            WHERE c.id IN ({placeholders}) 
            AND c.is_default = 0 
            AND i.category_id IS NULL
        ''', category_ids).fetchall()
        
        if not deletable_categories:
            conn.close()
            return jsonify({
                'status': 'error', 
                'message': 'No deletable categories found. Categories must be custom (non-default) and have no inventory items.'
            }), 400
        
        # Delete the categories
        deletable_ids = [cat['id'] for cat in deletable_categories]
        placeholders = ','.join(['?' for _ in deletable_ids])
        conn.execute(f'DELETE FROM categories WHERE id IN ({placeholders})', deletable_ids)
        
        affected_rows = conn.total_changes
        conn.commit()
        conn.close()
        
        return jsonify({
            'status': 'success',
            'message': f'Successfully deleted {affected_rows} categor{"y" if affected_rows == 1 else "ies"}',
            'deleted_categories': [dict(cat) for cat in deletable_categories],
            'affected_count': affected_rows
        })
        
    except Exception as e:
        return jsonify({'status': 'error', 'message': str(e)}), 500

@categories_bp.route('/categories/icons', methods=['GET'])
def get_available_icons():
    """Get list of available FontAwesome icons for categories"""
    # Common FontAwesome icons suitable for device categories
    available_icons = [
        {'value': 'fas fa-desktop', 'label': 'Desktop', 'group': 'Computers'},
        {'value': 'fas fa-laptop', 'label': 'Laptop', 'group': 'Computers'},
        {'value': 'fas fa-server', 'label': 'Server', 'group': 'Computers'},
        {'value': 'fas fa-mobile-alt', 'label': 'Mobile Device', 'group': 'Mobile'},
        {'value': 'fas fa-tablet-alt', 'label': 'Tablet', 'group': 'Mobile'},
        
        {'value': 'fas fa-route', 'label': 'Router', 'group': 'Network'},
        {'value': 'fas fa-network-wired', 'label': 'Switch/Hub', 'group': 'Network'},
        {'value': 'fas fa-wifi', 'label': 'WiFi/Wireless', 'group': 'Network'},
        {'value': 'fas fa-satellite-dish', 'label': 'Antenna/Satellite', 'group': 'Network'},
        
        {'value': 'fas fa-home', 'label': 'Smart Home', 'group': 'Smart Home'},
        {'value': 'fas fa-lightbulb', 'label': 'Lighting', 'group': 'Smart Home'},
        {'value': 'fas fa-thermometer-half', 'label': 'Climate Control', 'group': 'Smart Home'},
        {'value': 'fas fa-shield-alt', 'label': 'Security', 'group': 'Smart Home'},
        {'value': 'fas fa-camera', 'label': 'Camera', 'group': 'Smart Home'},
        {'value': 'fas fa-microchip', 'label': 'IoT Device', 'group': 'Smart Home'},
        
        {'value': 'fas fa-tv', 'label': 'Television', 'group': 'Entertainment'},
        {'value': 'fas fa-music', 'label': 'Audio/Music', 'group': 'Entertainment'},
        {'value': 'fas fa-gamepad', 'label': 'Gaming', 'group': 'Entertainment'},
        {'value': 'fas fa-headphones', 'label': 'Headphones', 'group': 'Entertainment'},
        
        {'value': 'fas fa-print', 'label': 'Printer', 'group': 'Office'},
        {'value': 'fas fa-keyboard', 'label': 'Input Device', 'group': 'Office'},
        {'value': 'fas fa-mouse', 'label': 'Mouse', 'group': 'Office'},
        {'value': 'fas fa-scanner', 'label': 'Scanner', 'group': 'Office'},
        
        {'value': 'fas fa-plug', 'label': 'Power/Electrical', 'group': 'Appliances'},
        {'value': 'fas fa-blender', 'label': 'Kitchen Appliance', 'group': 'Appliances'},
        {'value': 'fas fa-fan', 'label': 'Fan/Cooling', 'group': 'Appliances'},
        {'value': 'fas fa-tools', 'label': 'Tools', 'group': 'Appliances'},
        
        {'value': 'fas fa-car', 'label': 'Automotive', 'group': 'Other'},
        {'value': 'fas fa-warehouse', 'label': 'Storage', 'group': 'Other'},
        {'value': 'fas fa-clock', 'label': 'Clock/Timer', 'group': 'Other'},
        {'value': 'fas fa-question', 'label': 'Other/Unknown', 'group': 'Other'}
    ]
    
    return jsonify({
        'status': 'success',
        'icons': available_icons
    })

@categories_bp.route('/categories/colors', methods=['GET'])
def get_available_colors():
    """Get list of predefined colors for categories"""
    # Modern, accessible color palette
    available_colors = [
        {'value': '#0d6efd', 'label': 'Primary Blue', 'group': 'Blues'},
        {'value': '#0dcaf0', 'label': 'Info Cyan', 'group': 'Blues'},
        {'value': '#20c997', 'label': 'Teal', 'group': 'Blues'},
        {'value': '#198754', 'label': 'Success Green', 'group': 'Greens'},
        {'value': '#28a745', 'label': 'Forest Green', 'group': 'Greens'},
        {'value': '#6f42c1', 'label': 'Purple', 'group': 'Purples'},
        {'value': '#d63384', 'label': 'Pink', 'group': 'Purples'},
        {'value': '#fd7e14', 'label': 'Orange', 'group': 'Warm'},
        {'value': '#ffc107', 'label': 'Warning Yellow', 'group': 'Warm'},
        {'value': '#dc3545', 'label': 'Danger Red', 'group': 'Warm'},
        {'value': '#6c757d', 'label': 'Gray', 'group': 'Neutrals'},
        {'value': '#495057', 'label': 'Dark Gray', 'group': 'Neutrals'},
        {'value': '#343a40', 'label': 'Almost Black', 'group': 'Neutrals'}
    ]
    
    return jsonify({
        'status': 'success',
        'colors': available_colors
    })

@categories_bp.route('/categories/validate', methods=['POST'])
def validate_category():
    """Validate category data before saving"""
    try:
        data = request.get_json()
        
        if not data:
            return jsonify({'status': 'error', 'message': 'No data provided'}), 400
        
        errors = []
        warnings = []
        
        # Validate name
        name = data.get('name', '').strip()
        if not name:
            errors.append('Category name is required')
        elif len(name) < 2:
            errors.append('Category name must be at least 2 characters')
        elif len(name) > 50:
            errors.append('Category name must be less than 50 characters')
        else:
            # Check for duplicate names
            conn = get_db_connection()
            category_id = data.get('id')  # For updates
            if category_id:
                existing = conn.execute(
                    'SELECT id FROM categories WHERE LOWER(name) = LOWER(?) AND id != ?', 
                    (name, category_id)
                ).fetchone()
            else:
                existing = conn.execute(
                    'SELECT id FROM categories WHERE LOWER(name) = LOWER(?)', 
                    (name,)
                ).fetchone()
            conn.close()
            
            if existing:
                errors.append('A category with this name already exists')
        
        # Validate description
        description = data.get('description', '')
        if description and len(description) > 255:
            warnings.append('Description is quite long. Consider keeping it under 255 characters.')
        
        # Validate icon
        icon = data.get('icon', '')
        if icon and not icon.startswith('fas fa-'):
            warnings.append('Icon should be a FontAwesome class (e.g., "fas fa-desktop")')
        
        # Validate color
        color = data.get('color', '')
        if color and not color.startswith('#'):
            warnings.append('Color should be a hex color code (e.g., "#0d6efd")')
        elif color and len(color) != 7:
            warnings.append('Color should be a 6-digit hex color code (e.g., "#0d6efd")')
        
        return jsonify({
            'status': 'success',
            'valid': len(errors) == 0,
            'errors': errors,
            'warnings': warnings
        })
        
    except Exception as e:
        return jsonify({'status': 'error', 'message': str(e)}), 500