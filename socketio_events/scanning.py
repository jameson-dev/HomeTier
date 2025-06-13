from flask_socketio import emit
from flask import request

def register_scanning_events(socketio, realtime_monitor, scanner):
    
    @socketio.on('connect')
    def handle_connect():
        print(f"Client connected: {request.sid}")
        emit('connected', {'message': 'Connected to HomeTier real-time updates'})
        
        if not realtime_monitor.monitoring_active:
            realtime_monitor.start_monitoring()

    @socketio.on('disconnect')
    def handle_disconnect():
        print(f"Client disconnected: {request.sid}")

    @socketio.on('start_network_scan')
    def handle_start_scan():
        """Handle real-time network scan with progress updates"""
        if realtime_monitor.scan_in_progress:
            emit('scan_error', {'message': 'Scan already in progress'})
            return
        
        realtime_monitor.start_scan()

    @socketio.on('request_device_status')
    def handle_device_status_request():
        """Send current device status to requesting client"""
        realtime_monitor.send_current_status()