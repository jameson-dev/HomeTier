# socketio_events/monitoring.py

from flask_socketio import emit
from flask import request
import json

def register_monitoring_events(socketio, realtime_monitor):
    """Register real-time monitoring SocketIO events"""
    
    @socketio.on('request_device_status')
    def handle_device_status_request():
        """Send current device status to requesting client"""
        print(f"Device status requested by client: {request.sid}")
        try:
            realtime_monitor.send_current_status()
        except Exception as e:
            print(f"Error sending device status: {e}")
            emit('error', {'message': f'Error getting device status: {str(e)}'})

    @socketio.on('request_monitoring_stats')
    def handle_monitoring_stats_request():
        """Send comprehensive monitoring statistics to client"""
        print(f"Monitoring stats requested by client: {request.sid}")
        try:
            stats = realtime_monitor.get_monitoring_stats()
            emit('monitoring_stats', {
                'stats': stats,
                'timestamp': realtime_monitor.get_current_timestamp()
            })
        except Exception as e:
            print(f"Error getting monitoring stats: {e}")
            emit('error', {'message': f'Error getting monitoring stats: {str(e)}'})

    @socketio.on('start_monitoring')
    def handle_start_monitoring():
        """Start real-time device monitoring"""
        print(f"Monitoring start requested by client: {request.sid}")
        try:
            if not realtime_monitor.monitoring_active:
                realtime_monitor.start_monitoring()
                emit('monitoring_started', {
                    'message': 'Real-time monitoring started',
                    'status': 'active'
                })
            else:
                emit('monitoring_status', {
                    'message': 'Monitoring already active',
                    'status': 'active'
                })
        except Exception as e:
            print(f"Error starting monitoring: {e}")
            emit('error', {'message': f'Error starting monitoring: {str(e)}'})

    @socketio.on('stop_monitoring')
    def handle_stop_monitoring():
        """Stop real-time device monitoring"""
        print(f"Monitoring stop requested by client: {request.sid}")
        try:
            if realtime_monitor.monitoring_active:
                realtime_monitor.stop_monitoring()
                emit('monitoring_stopped', {
                    'message': 'Real-time monitoring stopped',
                    'status': 'inactive'
                })
            else:
                emit('monitoring_status', {
                    'message': 'Monitoring already inactive',
                    'status': 'inactive'
                })
        except Exception as e:
            print(f"Error stopping monitoring: {e}")
            emit('error', {'message': f'Error stopping monitoring: {str(e)}'})

    @socketio.on('get_monitoring_status')
    def handle_get_monitoring_status():
        """Get current monitoring status"""
        try:
            status = realtime_monitor.get_scan_status()
            emit('monitoring_status', {
                'monitoring_active': status.get('monitoring_active', False),
                'scan_in_progress': status.get('scan_in_progress', False),
                'status': 'active' if status.get('monitoring_active', False) else 'inactive'
            })
        except Exception as e:
            print(f"Error getting monitoring status: {e}")
            emit('error', {'message': f'Error getting monitoring status: {str(e)}'})

    @socketio.on('request_network_health')
    def handle_network_health_request():
        """Send current network health metrics to client"""
        print(f"Network health requested by client: {request.sid}")
        try:
            from backend.database import get_db_connection
            from datetime import datetime
            
            conn = get_db_connection()
            
            # Get device status distribution
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
            
            # Calculate health score
            total_devices = conn.execute('SELECT COUNT(*) as count FROM devices WHERE is_ignored = 0').fetchone()['count']
            online_devices = conn.execute('''
                SELECT COUNT(*) as count FROM devices 
                WHERE is_ignored = 0 AND datetime(last_seen) > datetime('now', '-1 hour')
            ''').fetchone()['count']
            
            health_score = round((online_devices / total_devices * 100) if total_devices > 0 else 0, 1)
            
            conn.close()
            
            emit('network_health_update', {
                'device_status': [dict(row) for row in device_status],
                'health_score': health_score,
                'total_devices': total_devices,
                'online_devices': online_devices,
                'timestamp': datetime.now().isoformat()
            })
            
        except Exception as e:
            print(f"Error getting network health: {e}")
            emit('error', {'message': f'Error getting network health: {str(e)}'})

    @socketio.on('subscribe_to_alerts')
    def handle_subscribe_alerts():
        """Subscribe client to real-time alerts"""
        print(f"Client {request.sid} subscribed to alerts")
        try:
            # Add client to alerts room for targeted notifications
            from flask_socketio import join_room
            join_room('alerts')
            
            emit('subscription_confirmed', {
                'type': 'alerts',
                'message': 'Subscribed to real-time alerts'
            })
            
            # Send any immediate alerts
            realtime_monitor.send_immediate_alerts()
            
        except Exception as e:
            print(f"Error subscribing to alerts: {e}")
            emit('error', {'message': f'Error subscribing to alerts: {str(e)}'})

    @socketio.on('unsubscribe_from_alerts')
    def handle_unsubscribe_alerts():
        """Unsubscribe client from real-time alerts"""
        print(f"Client {request.sid} unsubscribed from alerts")
        try:
            from flask_socketio import leave_room
            leave_room('alerts')
            
            emit('subscription_cancelled', {
                'type': 'alerts',
                'message': 'Unsubscribed from real-time alerts'
            })
            
        except Exception as e:
            print(f"Error unsubscribing from alerts: {e}")
            emit('error', {'message': f'Error unsubscribing from alerts: {str(e)}'})

    @socketio.on('force_device_check')
    def handle_force_device_check():
        """Force an immediate device status check"""
        print(f"Forced device check requested by client: {request.sid}")
        try:
            if realtime_monitor.monitoring_active:
                # Trigger immediate status check
                realtime_monitor.check_device_status_changes()
                realtime_monitor.check_new_devices()
                
                emit('device_check_completed', {
                    'message': 'Device status check completed',
                    'timestamp': realtime_monitor.get_current_timestamp()
                })
            else:
                emit('error', {
                    'message': 'Monitoring must be active to perform device checks'
                })
                
        except Exception as e:
            print(f"Error in forced device check: {e}")
            emit('error', {'message': f'Error performing device check: {str(e)}'})

    @socketio.on('request_device_history')
    def handle_device_history_request(data):
        """Get device status history for a specific device"""
        try:
            device_id = data.get('device_id')
            hours = data.get('hours', 24)  # Default to 24 hours
            
            if not device_id:
                emit('error', {'message': 'Device ID is required'})
                return
            
            from backend.database import get_db_connection
            
            conn = get_db_connection()
            
            # Get device info and recent status changes
            device_info = conn.execute('''
                SELECT * FROM devices WHERE id = ?
            ''', (device_id,)).fetchone()
            
            if not device_info:
                emit('error', {'message': 'Device not found'})
                return
            
            # For now, return current status (could be enhanced with status history table)
            device_dict = dict(device_info)
            
            conn.close()
            
            emit('device_history', {
                'device_id': device_id,
                'device_info': device_dict,
                'history_hours': hours,
                'current_status': realtime_monitor.get_device_current_status(device_id),
                'timestamp': realtime_monitor.get_current_timestamp()
            })
            
        except Exception as e:
            print(f"Error getting device history: {e}")
            emit('error', {'message': f'Error getting device history: {str(e)}'})

    @socketio.on('ping_server')
    def handle_ping():
        """Handle client ping for connection testing"""
        emit('pong', {
            'timestamp': realtime_monitor.get_current_timestamp(),
            'monitoring_active': realtime_monitor.monitoring_active
        })

    @socketio.on('request_dashboard_data')
    def handle_dashboard_data_request():
        """Send comprehensive dashboard data to client"""
        print(f"Dashboard data requested by client: {request.sid}")
        try:
            from backend.database import get_db_connection
            
            conn = get_db_connection()
            
            # Get quick dashboard stats
            stats = conn.execute('''
                SELECT 
                    (SELECT COUNT(*) FROM devices WHERE is_ignored = 0) as total_devices,
                    (SELECT COUNT(*) FROM devices WHERE is_ignored = 0 AND datetime(last_seen) > datetime('now', '-1 hour')) as online_devices,
                    (SELECT COUNT(*) FROM inventory WHERE deleted_at IS NULL) as inventory_items,
                    (SELECT COUNT(*) FROM devices WHERE is_ignored = 0 AND datetime(first_seen) > datetime('now', '-24 hours')) as new_devices_24h
            ''').fetchone()
            
            conn.close()
            
            emit('dashboard_data_update', {
                'stats': dict(stats),
                'monitoring_status': {
                    'active': realtime_monitor.monitoring_active,
                    'scan_in_progress': realtime_monitor.scan_in_progress
                },
                'timestamp': realtime_monitor.get_current_timestamp()
            })
            
        except Exception as e:
            print(f"Error getting dashboard data: {e}")
            emit('error', {'message': f'Error getting dashboard data: {str(e)}'})

    # Add these methods to RealtimeMonitor class if they don't exist
    def add_missing_methods_to_monitor():
        """Add missing utility methods to RealtimeMonitor if needed"""
        
        if not hasattr(realtime_monitor, 'get_current_timestamp'):
            def get_current_timestamp():
                from datetime import datetime
                return datetime.now().isoformat()
            realtime_monitor.get_current_timestamp = get_current_timestamp
        
        if not hasattr(realtime_monitor, 'send_immediate_alerts'):
            def send_immediate_alerts():
                # Send any critical alerts immediately upon subscription
                try:
                    from backend.database import get_db_connection
                    conn = get_db_connection()
                    
                    # Check for critical warranty alerts
                    critical_alerts = conn.execute('''
                        SELECT name, warranty_expiry
                        FROM inventory 
                        WHERE deleted_at IS NULL 
                        AND warranty_expiry IS NOT NULL
                        AND DATE(warranty_expiry) < DATE('now')
                        LIMIT 3
                    ''').fetchall()
                    
                    conn.close()
                    
                    if critical_alerts:
                        socketio.emit('immediate_alerts', {
                            'alerts': [dict(alert) for alert in critical_alerts],
                            'type': 'warranty_expired',
                            'count': len(critical_alerts)
                        }, room='alerts')
                        
                except Exception as e:
                    print(f"Error sending immediate alerts: {e}")
            
            realtime_monitor.send_immediate_alerts = send_immediate_alerts
        
        if not hasattr(realtime_monitor, 'get_device_current_status'):
            def get_device_current_status(device_id):
                try:
                    from backend.database import get_db_connection
                    from datetime import datetime
                    
                    conn = get_db_connection()
                    device = conn.execute('SELECT * FROM devices WHERE id = ?', (device_id,)).fetchone()
                    conn.close()
                    
                    if not device:
                        return 'unknown'
                    
                    device_dict = dict(device)
                    last_seen_str = device_dict['last_seen']
                    
                    if last_seen_str:
                        try:
                            last_seen = datetime.fromisoformat(last_seen_str.replace('Z', '+00:00'))
                        except:
                            last_seen = datetime.fromisoformat(last_seen_str)
                    else:
                        return 'unknown'
                    
                    time_diff = (datetime.now() - last_seen).total_seconds()
                    if time_diff < 3600:
                        return 'online'
                    elif time_diff < 86400:
                        return 'unknown'
                    else:
                        return 'offline'
                        
                except Exception:
                    return 'unknown'
            
            realtime_monitor.get_device_current_status = get_device_current_status
    
    # Add missing methods
    add_missing_methods_to_monitor()
    
    print("Monitoring SocketIO events registered successfully")