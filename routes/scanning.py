from flask import Blueprint, jsonify
from backend.database import get_db_connection

scanning_bp = Blueprint('scanning', __name__)

@scanning_bp.route('/scan', methods=['POST'])
def trigger_scan():
    """Trigger a network scan with real-time progress"""
    try:
        from flask import current_app
        # Get scanner and realtime_monitor from app context
        scanner = current_app.scanner
        realtime_monitor = current_app.realtime_monitor
        
        # Trigger the scan
        realtime_monitor.start_scan()
        
        return jsonify({
            'status': 'success',
            'message': 'Network scan started. Watch for real-time updates.'
        })
    except Exception as e:
        return jsonify({'status': 'error', 'message': str(e)}), 500

@scanning_bp.route('/scanning/stats', methods=['GET'])
def get_scanning_stats():
    """Get scanning-specific statistics"""
    try:
        conn = get_db_connection()
        
        total_devices = conn.execute('SELECT COUNT(*) as count FROM devices').fetchone()['count']
        managed_devices = conn.execute('''
            SELECT COUNT(*) as count FROM devices d
            INNER JOIN inventory i ON d.id = i.device_id
            WHERE i.deleted_at IS NULL
        ''').fetchone()['count']
        unmanaged_devices = conn.execute('''
            SELECT COUNT(*) as count FROM devices d
            LEFT JOIN inventory i ON d.id = i.device_id
            WHERE (i.device_id IS NULL OR i.deleted_at IS NOT NULL)
            AND d.is_ignored = 0
        ''').fetchone()['count']
        ignored_devices = conn.execute('''
            SELECT COUNT(*) as count FROM devices 
            WHERE is_ignored = 1
        ''').fetchone()['count']
        
        conn.close()
        
        return jsonify({
            'total_devices': total_devices,
            'managed_devices': managed_devices,
            'unmanaged_devices': unmanaged_devices,
            'ignored_devices': ignored_devices
        })
    except Exception as e:
        return jsonify({'status': 'error', 'message': str(e)}), 500