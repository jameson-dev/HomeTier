# routes/dashboard.py

from flask import Blueprint, request, jsonify
from backend.database import get_db_connection
from datetime import datetime, timedelta
import json

dashboard_bp = Blueprint('dashboard', __name__)

@dashboard_bp.route('/dashboard/stats', methods=['GET'])
def get_dashboard_stats():
    """Get comprehensive dashboard statistics including category breakdown and warranty alerts"""
    try:
        conn = get_db_connection()
        
        # Category statistics with proper joins
        category_stats = conn.execute('''
            SELECT 
                COALESCE(c.name, i.category, 'Uncategorized') as category,
                COUNT(*) as count,
                COALESCE(c.color, '#6c757d') as color,
                COALESCE(c.icon, 'fas fa-question') as icon,
                COALESCE(SUM(CAST(i.price as REAL)), 0) as total_value
            FROM inventory i
            LEFT JOIN categories c ON i.category_id = c.id
            WHERE i.deleted_at IS NULL 
            GROUP BY COALESCE(c.name, i.category, 'Uncategorized')
            ORDER BY count DESC
        ''').fetchall()
        
        # Warranty alerts (expiring in 30 days or expired)
        warranty_alerts = conn.execute('''
            SELECT name, warranty_expiry,
                   CASE 
                       WHEN warranty_expiry < date('now') THEN 'expired'
                       WHEN warranty_expiry <= date('now', '+30 days') THEN 'expiring'
                       ELSE 'active'
                   END as status
            FROM inventory 
            WHERE deleted_at IS NULL 
            AND warranty_expiry IS NOT NULL
            AND warranty_expiry <= date('now', '+30 days')
            ORDER BY warranty_expiry ASC
        ''').fetchall()
        
        conn.close()
        
        result = {
            'category_stats': [dict(row) for row in category_stats],
            'warranty_alerts': [dict(row) for row in warranty_alerts]
        }
        
        return jsonify(result)
        
    except Exception as e:
        print(f"Error in dashboard stats: {e}")
        return jsonify({'status': 'error', 'message': str(e)}), 500

@dashboard_bp.route('/dashboard/overview', methods=['GET'])
def get_dashboard_overview():
    """Get high-level dashboard overview metrics"""
    try:
        conn = get_db_connection()
        
        # Device counts and status
        device_stats = conn.execute('''
            SELECT 
                COUNT(*) as total_devices,
                COUNT(CASE WHEN is_ignored = 0 THEN 1 END) as active_devices,
                COUNT(CASE WHEN is_ignored = 1 THEN 1 END) as ignored_devices,
                COUNT(CASE WHEN datetime(first_seen) > datetime('now', '-24 hours') THEN 1 END) as new_devices_24h,
                COUNT(CASE WHEN datetime(last_seen) > datetime('now', '-1 hour') THEN 1 END) as online_devices,
                COUNT(CASE WHEN datetime(last_seen) <= datetime('now', '-24 hours') THEN 1 END) as offline_devices
            FROM devices
        ''').fetchone()
        
        # Inventory counts and value
        inventory_stats = conn.execute('''
            SELECT 
                COUNT(*) as total_items,
                COUNT(CASE WHEN device_id IS NOT NULL THEN 1 END) as networked_items,
                COUNT(CASE WHEN device_id IS NULL THEN 1 END) as manual_items,
                COUNT(CASE WHEN price IS NOT NULL AND CAST(price as REAL) > 0 THEN 1 END) as items_with_price,
                COALESCE(SUM(CAST(price as REAL)), 0) as total_value,
                COUNT(CASE WHEN datetime(created_at) > datetime('now', '-30 days') THEN 1 END) as recent_additions
            FROM inventory 
            WHERE deleted_at IS NULL
        ''').fetchone()
        
        # Warranty status breakdown
        warranty_stats = conn.execute('''
            SELECT 
                COUNT(CASE WHEN warranty_expiry IS NULL THEN 1 END) as unknown_warranty,
                COUNT(CASE WHEN warranty_expiry IS NOT NULL AND DATE(warranty_expiry) > DATE('now') THEN 1 END) as active_warranty,
                COUNT(CASE WHEN warranty_expiry IS NOT NULL AND DATE(warranty_expiry) < DATE('now') THEN 1 END) as expired_warranty,
                COUNT(CASE WHEN warranty_expiry IS NOT NULL AND DATE(warranty_expiry) BETWEEN DATE('now') AND DATE('now', '+30 days') THEN 1 END) as expiring_warranty
            FROM inventory
            WHERE deleted_at IS NULL
        ''').fetchone()
        
        # Recent activity
        recent_activity = conn.execute('''
            SELECT 
                'device' as type,
                hostname || ' (' || ip_address || ')' as description,
                first_seen as timestamp,
                'discovered' as action
            FROM devices 
            WHERE datetime(first_seen) > datetime('now', '-7 days')
            
            UNION ALL
            
            SELECT 
                'inventory' as type,
                name as description,
                created_at as timestamp,
                'added' as action
            FROM inventory 
            WHERE deleted_at IS NULL 
            AND datetime(created_at) > datetime('now', '-7 days')
            
            ORDER BY timestamp DESC
            LIMIT 10
        ''').fetchall()
        
        conn.close()
        
        return jsonify({
            'status': 'success',
            'overview': {
                'devices': dict(device_stats),
                'inventory': dict(inventory_stats),
                'warranty': dict(warranty_stats),
                'recent_activity': [dict(row) for row in recent_activity]
            }
        })
        
    except Exception as e:
        return jsonify({'status': 'error', 'message': str(e)}), 500

@dashboard_bp.route('/dashboard/network-health', methods=['GET'])
def get_network_health():
    """Get network health metrics for dashboard"""
    try:
        conn = get_db_connection()
        
        # Device status distribution
        device_status = conn.execute('''
            SELECT 
                CASE 
                    WHEN datetime(last_seen) > datetime('now', '-1 hour') THEN 'online'
                    WHEN datetime(last_seen) > datetime('now', '-1 day') THEN 'unknown'
                    ELSE 'offline'
                END as status,
                COUNT(*) as count
            FROM devices
            WHERE is_ignored = 0
            GROUP BY status
        ''').fetchall()
        
        # Network coverage by IP ranges
        network_ranges = conn.execute('''
            SELECT 
                SUBSTR(ip_address, 1, INSTR(ip_address || '.', '.', INSTR(ip_address || '.', '.', INSTR(ip_address || '.', '.') + 1)) - 1) as network_prefix,
                COUNT(*) as device_count,
                COUNT(CASE WHEN datetime(last_seen) > datetime('now', '-1 hour') THEN 1 END) as online_count
            FROM devices 
            WHERE ip_address IS NOT NULL AND is_ignored = 0
            GROUP BY network_prefix
            ORDER BY device_count DESC
            LIMIT 10
        ''').fetchall()
        
        # Vendor distribution
        vendor_stats = conn.execute('''
            SELECT 
                COALESCE(vendor, 'Unknown') as vendor,
                COUNT(*) as count,
                COUNT(CASE WHEN datetime(last_seen) > datetime('now', '-1 hour') THEN 1 END) as online_count
            FROM devices
            WHERE is_ignored = 0
            GROUP BY vendor
            ORDER BY count DESC
            LIMIT 10
        ''').fetchall()
        
        # Network health score calculation
        total_devices = conn.execute('SELECT COUNT(*) as count FROM devices WHERE is_ignored = 0').fetchone()['count']
        online_devices = conn.execute('''
            SELECT COUNT(*) as count FROM devices 
            WHERE is_ignored = 0 AND datetime(last_seen) > datetime('now', '-1 hour')
        ''').fetchone()['count']
        
        health_score = round((online_devices / total_devices * 100) if total_devices > 0 else 0, 1)
        
        conn.close()
        
        return jsonify({
            'status': 'success',
            'network_health': {
                'device_status': [dict(row) for row in device_status],
                'network_ranges': [dict(row) for row in network_ranges],
                'vendor_distribution': [dict(row) for row in vendor_stats],
                'health_score': health_score,
                'total_devices': total_devices,
                'online_devices': online_devices
            }
        })
        
    except Exception as e:
        return jsonify({'status': 'error', 'message': str(e)}), 500

@dashboard_bp.route('/dashboard/inventory-metrics', methods=['GET'])
def get_inventory_metrics():
    """Get inventory value and metrics"""
    try:
        conn = get_db_connection()
        
        # Inventory values by category
        inventory_values = conn.execute('''
            SELECT 
                COALESCE(c.name, i.category, 'Unknown') as category,
                COALESCE(c.color, '#6c757d') as color,
                COALESCE(c.icon, 'fas fa-question') as icon,
                COUNT(i.id) as item_count,
                COALESCE(SUM(CAST(i.price as REAL)), 0) as total_value,
                COALESCE(AVG(CAST(i.price as REAL)), 0) as avg_value,
                COALESCE(MAX(CAST(i.price as REAL)), 0) as max_value
            FROM inventory i
            LEFT JOIN categories c ON i.category_id = c.id
            WHERE i.deleted_at IS NULL 
            AND i.price IS NOT NULL 
            AND CAST(i.price as REAL) > 0
            GROUP BY COALESCE(c.name, i.category, 'Unknown')
            ORDER BY total_value DESC
        ''').fetchall()
        
        # Warranty status breakdown
        warranty_status = conn.execute('''
            SELECT 
                CASE 
                    WHEN warranty_expiry IS NULL THEN 'unknown'
                    WHEN DATE(warranty_expiry) < DATE('now') THEN 'expired'
                    WHEN DATE(warranty_expiry) <= DATE('now', '+30 days') THEN 'expiring'
                    ELSE 'active'
                END as status,
                COUNT(*) as count,
                COALESCE(SUM(CAST(price as REAL)), 0) as total_value
            FROM inventory
            WHERE deleted_at IS NULL
            GROUP BY status
        ''').fetchall()
        
        # Recent additions and their value
        recent_additions = conn.execute('''
            SELECT 
                COUNT(*) as count,
                COALESCE(SUM(CAST(price as REAL)), 0) as total_value
            FROM inventory
            WHERE deleted_at IS NULL
            AND datetime(created_at) > datetime('now', '-30 days')
        ''').fetchone()
        
        # Most valuable items
        top_items = conn.execute('''
            SELECT name, CAST(price as REAL) as price, category
            FROM inventory
            WHERE deleted_at IS NULL 
            AND price IS NOT NULL 
            AND CAST(price as REAL) > 0
            ORDER BY CAST(price as REAL) DESC
            LIMIT 5
        ''').fetchall()
        
        conn.close()
        
        return jsonify({
            'status': 'success',
            'inventory_metrics': {
                'category_values': [dict(row) for row in inventory_values],
                'warranty_status': [dict(row) for row in warranty_status],
                'recent_additions': dict(recent_additions),
                'top_valuable_items': [dict(row) for row in top_items]
            }
        })
        
    except Exception as e:
        return jsonify({'status': 'error', 'message': str(e)}), 500

@dashboard_bp.route('/dashboard/timeline', methods=['GET'])
def get_dashboard_timeline():
    """Get timeline data for device discovery and inventory additions"""
    try:
        days = request.args.get('days', 30, type=int)
        days = max(1, min(days, 365))  # Limit between 1 and 365 days
        
        conn = get_db_connection()
        
        # Device discovery timeline
        device_timeline = conn.execute('''
            SELECT 
                DATE(first_seen) as date,
                COUNT(*) as devices_discovered
            FROM devices 
            WHERE datetime(first_seen) > datetime('now', '-{} days')
            GROUP BY DATE(first_seen)
            ORDER BY date ASC
        '''.format(days)).fetchall()
        
        # Inventory additions timeline
        inventory_timeline = conn.execute('''
            SELECT 
                DATE(created_at) as date,
                COUNT(*) as items_added,
                COALESCE(SUM(CAST(price as REAL)), 0) as value_added
            FROM inventory 
            WHERE deleted_at IS NULL 
            AND datetime(created_at) > datetime('now', '-{} days')
            GROUP BY DATE(created_at)
            ORDER BY date ASC
        '''.format(days)).fetchall()
        
        conn.close()
        
        # Fill in missing dates with zero counts
        start_date = datetime.now() - timedelta(days=days)
        timeline = []
        
        device_dict = {row['date']: row['devices_discovered'] for row in device_timeline}
        inventory_dict = {row['date']: {'items_added': row['items_added'], 'value_added': row['value_added']} for row in inventory_timeline}
        
        for i in range(days + 1):
            current_date = start_date + timedelta(days=i)
            date_str = current_date.strftime('%Y-%m-%d')
            timeline.append({
                'date': date_str,
                'devices_discovered': device_dict.get(date_str, 0),
                'items_added': inventory_dict.get(date_str, {}).get('items_added', 0),
                'value_added': round(inventory_dict.get(date_str, {}).get('value_added', 0), 2)
            })
        
        return jsonify({
            'status': 'success',
            'timeline': timeline,
            'period_days': days
        })
        
    except Exception as e:
        return jsonify({'status': 'error', 'message': str(e)}), 500

@dashboard_bp.route('/dashboard/alerts', methods=['GET'])
def get_dashboard_alerts():
    """Get important alerts and notifications for the dashboard"""
    try:
        conn = get_db_connection()
        
        alerts = []
        
        # Warranty expiration alerts
        warranty_alerts = conn.execute('''
            SELECT name, warranty_expiry, 
                   julianday(warranty_expiry) - julianday('now') as days_remaining
            FROM inventory 
            WHERE deleted_at IS NULL 
            AND warranty_expiry IS NOT NULL
            AND DATE(warranty_expiry) <= DATE('now', '+30 days')
            ORDER BY warranty_expiry ASC
        ''').fetchall()
        
        for alert in warranty_alerts:
            days_remaining = int(alert['days_remaining'])
            if days_remaining < 0:
                alerts.append({
                    'type': 'warranty_expired',
                    'severity': 'high',
                    'title': 'Warranty Expired',
                    'message': f"Warranty for '{alert['name']}' expired {abs(days_remaining)} days ago",
                    'item_name': alert['name'],
                    'date': alert['warranty_expiry']
                })
            else:
                alerts.append({
                    'type': 'warranty_expiring',
                    'severity': 'medium',
                    'title': 'Warranty Expiring Soon',
                    'message': f"Warranty for '{alert['name']}' expires in {days_remaining} days",
                    'item_name': alert['name'],
                    'date': alert['warranty_expiry']
                })
        
        # Device offline alerts (devices that haven't been seen in 24+ hours)
        offline_devices = conn.execute('''
            SELECT hostname, ip_address, mac_address,
                   datetime(last_seen) as last_seen,
                   (julianday('now') - julianday(last_seen)) as days_offline
            FROM devices 
            WHERE is_ignored = 0
            AND datetime(last_seen) <= datetime('now', '-24 hours')
            ORDER BY last_seen ASC
            LIMIT 10
        ''').fetchall()
        
        for device in offline_devices:
            days_offline = int(device['days_offline'])
            device_name = device['hostname'] or device['ip_address'] or 'Unknown Device'
            
            if days_offline >= 7:
                severity = 'high'
                title = 'Device Long Term Offline'
            elif days_offline >= 3:
                severity = 'medium'
                title = 'Device Extended Offline'
            else:
                severity = 'low'
                title = 'Device Offline'
            
            alerts.append({
                'type': 'device_offline',
                'severity': severity,
                'title': title,
                'message': f"'{device_name}' has been offline for {days_offline} days",
                'device_name': device_name,
                'ip_address': device['ip_address'],
                'last_seen': device['last_seen']
            })
        
        # New devices requiring attention
        new_devices = conn.execute('''
            SELECT d.hostname, d.ip_address, d.vendor, d.first_seen
            FROM devices d
            LEFT JOIN inventory i ON d.id = i.device_id AND i.deleted_at IS NULL
            WHERE d.is_ignored = 0 
            AND i.device_id IS NULL
            AND datetime(d.first_seen) > datetime('now', '-7 days')
            ORDER BY d.first_seen DESC
            LIMIT 5
        ''').fetchall()
        
        for device in new_devices:
            device_name = device['hostname'] or device['ip_address'] or 'Unknown Device'
            alerts.append({
                'type': 'new_device',
                'severity': 'info',
                'title': 'New Device Discovered',
                'message': f"'{device_name}' was discovered but not added to inventory",
                'device_name': device_name,
                'vendor': device['vendor'],
                'first_seen': device['first_seen']
            })
        
        # Inventory without network connection
        orphaned_inventory = conn.execute('''
            SELECT name, created_at
            FROM inventory 
            WHERE deleted_at IS NULL 
            AND device_id IS NULL
            AND datetime(created_at) > datetime('now', '-30 days')
            ORDER BY created_at DESC
            LIMIT 3
        ''').fetchall()
        
        for item in orphaned_inventory:
            alerts.append({
                'type': 'orphaned_inventory',
                'severity': 'low',
                'title': 'Inventory Item Not Networked',
                'message': f"'{item['name']}' is not linked to any network device",
                'item_name': item['name'],
                'created_at': item['created_at']
            })
        
        conn.close()
        
        # Sort alerts by severity and date
        severity_order = {'high': 0, 'medium': 1, 'low': 2, 'info': 3}
        alerts.sort(key=lambda x: (severity_order.get(x['severity'], 4), x.get('date', x.get('last_seen', x.get('first_seen', x.get('created_at', ''))))))
        
        return jsonify({
            'status': 'success',
            'alerts': alerts[:20],  # Limit to 20 most important alerts
            'summary': {
                'total_alerts': len(alerts),
                'high_severity': len([a for a in alerts if a['severity'] == 'high']),
                'medium_severity': len([a for a in alerts if a['severity'] == 'medium']),
                'low_severity': len([a for a in alerts if a['severity'] == 'low']),
                'info_alerts': len([a for a in alerts if a['severity'] == 'info'])
            }
        })
        
    except Exception as e:
        return jsonify({'status': 'error', 'message': str(e)}), 500

@dashboard_bp.route('/dashboard/quick-stats', methods=['GET'])
def get_quick_stats():
    """Get quick statistics for dashboard cards/widgets"""
    try:
        conn = get_db_connection()
        
        # Quick counts for dashboard cards
        stats = conn.execute('''
            SELECT 
                (SELECT COUNT(*) FROM devices WHERE is_ignored = 0) as total_devices,
                (SELECT COUNT(*) FROM devices WHERE is_ignored = 0 AND datetime(last_seen) > datetime('now', '-1 hour')) as online_devices,
                (SELECT COUNT(*) FROM inventory WHERE deleted_at IS NULL) as inventory_items,
                (SELECT COUNT(*) FROM devices WHERE is_ignored = 0 AND datetime(first_seen) > datetime('now', '-24 hours')) as new_devices_24h,
                (SELECT COALESCE(SUM(CAST(price as REAL)), 0) FROM inventory WHERE deleted_at IS NULL AND price IS NOT NULL) as total_inventory_value,
                (SELECT COUNT(*) FROM inventory WHERE deleted_at IS NULL AND warranty_expiry IS NOT NULL AND DATE(warranty_expiry) <= DATE('now', '+30 days')) as warranty_alerts
        ''').fetchone()
        
        # Last scan time
        last_scan = conn.execute('''
            SELECT MAX(last_seen) as last_scan_time
            FROM devices
        ''').fetchone()
        
        conn.close()
        
        return jsonify({
            'status': 'success',
            'quick_stats': {
                'total_devices': stats['total_devices'],
                'online_devices': stats['online_devices'],
                'inventory_items': stats['inventory_items'],
                'new_devices_24h': stats['new_devices_24h'],
                'total_inventory_value': round(stats['total_inventory_value'], 2),
                'warranty_alerts': stats['warranty_alerts'],
                'last_scan_time': last_scan['last_scan_time'],
                'network_health_percentage': round((stats['online_devices'] / stats['total_devices'] * 100) if stats['total_devices'] > 0 else 0, 1)
            }
        })
        
    except Exception as e:
        return jsonify({'status': 'error', 'message': str(e)}), 500