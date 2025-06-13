import threading
import time
from datetime import datetime
from backend.database import get_db_connection, add_device

class RealtimeMonitor:
    def __init__(self, socketio, scanner):
        self.socketio = socketio
        self.scanner = scanner
        self.previous_device_status = {}
        self.scan_in_progress = False
        self.monitoring_active = False
        
    def start_monitoring(self):
        """Start real-time device monitoring"""
        if self.monitoring_active:
            return
            
        self.monitoring_active = True
        
        def monitor_loop():
            while self.monitoring_active:
                try:
                    self.check_device_status_changes()
                    self.check_new_devices()
                    time.sleep(15)  # Check every 15 seconds
                except Exception as e:
                    print(f"Error in monitoring loop: {e}")
                    time.sleep(30)
                    
        monitor_thread = threading.Thread(target=monitor_loop, daemon=True)
        monitor_thread.start()
        print("Real-time monitoring started")
        
    def stop_monitoring(self):
        """Stop real-time monitoring"""
        self.monitoring_active = False
        
    def check_device_status_changes(self):
        """Check for device status changes and emit updates"""
        try:
            conn = get_db_connection()
            devices = conn.execute('SELECT * FROM devices').fetchall()
            conn.close()
            
            current_status = {}
            status_changes = []
            now = datetime.now()
            
            for device in devices:
                device_dict = dict(device)
                device_id = device_dict['id']
                last_seen_str = device_dict['last_seen']
                
                if last_seen_str:
                    try:
                        last_seen = datetime.fromisoformat(last_seen_str.replace('Z', '+00:00'))
                    except:
                        last_seen = datetime.fromisoformat(last_seen_str)
                else:
                    last_seen = now
                
                time_diff = (now - last_seen).total_seconds()
                if time_diff < 3600:
                    status = 'online'
                elif time_diff < 86400:
                    status = 'unknown'
                else:
                    status = 'offline'
                
                current_status[device_id] = {
                    'status': status,
                    'last_seen': device_dict['last_seen'],
                    'ip_address': device_dict['ip_address'],
                    'hostname': device_dict['hostname'],
                    'vendor': device_dict['vendor']
                }
                
                if device_id in self.previous_device_status:
                    old_status = self.previous_device_status[device_id]['status']
                    if old_status != status:
                        status_changes.append({
                            'device_id': device_id,
                            'device_info': current_status[device_id],
                            'old_status': old_status,
                            'new_status': status,
                            'timestamp': now.isoformat()
                        })
            
            if status_changes:
                self.socketio.emit('device_status_changes', {
                    'changes': status_changes,
                    'timestamp': now.isoformat()
                })
                
            self.previous_device_status = current_status
            
            status_counts = {'online': 0, 'offline': 0, 'unknown': 0}
            for device_status in current_status.values():
                status_counts[device_status['status']] += 1
                
            self.socketio.emit('device_status_counts', status_counts)
            
        except Exception as e:
            print(f"Error checking device status: {e}")
            
    def check_new_devices(self):
        """Check for newly discovered devices"""
        try:
            conn = get_db_connection()
            recent_devices = conn.execute('''
                SELECT * FROM devices 
                WHERE datetime(first_seen) > datetime('now', '-1 minute')
                ORDER BY first_seen DESC
            ''').fetchall()
            conn.close()
            
            if recent_devices:
                new_devices = []
                for device in recent_devices:
                    device_dict = dict(device)
                    new_devices.append({
                        'id': device_dict['id'],
                        'ip_address': device_dict['ip_address'],
                        'mac_address': device_dict['mac_address'],
                        'hostname': device_dict['hostname'],
                        'vendor': device_dict['vendor'],
                        'first_seen': device_dict['first_seen']
                    })
                
                self.socketio.emit('new_devices_discovered', {
                    'devices': new_devices,
                    'count': len(new_devices),
                    'timestamp': datetime.now().isoformat()
                })
                
        except Exception as e:
            print(f"Error checking new devices: {e}")

    def send_current_status(self):
        """Send current device status to requesting client"""
        try:
            conn = get_db_connection()
            devices = conn.execute('SELECT * FROM devices').fetchall()
            conn.close()
            
            status_counts = {'online': 0, 'offline': 0, 'unknown': 0}
            now = datetime.now()
            
            for device in devices:
                device_dict = dict(device)
                last_seen_str = device_dict['last_seen']
                
                if last_seen_str:
                    try:
                        last_seen = datetime.fromisoformat(last_seen_str.replace('Z', '+00:00'))
                    except:
                        last_seen = datetime.fromisoformat(last_seen_str)
                else:
                    last_seen = now
                    
                time_diff = (now - last_seen).total_seconds()
                
                if time_diff < 3600:
                    status_counts['online'] += 1
                elif time_diff < 86400:
                    status_counts['unknown'] += 1
                else:
                    status_counts['offline'] += 1
                    
            self.socketio.emit('device_status_counts', status_counts)
            
        except Exception as e:
            print(f"Error getting device status: {e}")
            self.socketio.emit('error', {'message': f'Error getting device status: {str(e)}'})

    def start_scan(self):
        """Start network scan with real-time progress"""
        if self.scan_in_progress:
            self.socketio.emit('scan_error', {'message': 'Scan already in progress'})
            return
            
        def scan_with_progress():
            try:
                self.scan_in_progress = True
                self.socketio.emit('scan_started', {
                    'message': 'Network scan started', 
                    'timestamp': datetime.now().isoformat()
                })
                
                network_ranges = self.scanner.get_network_ranges()
                all_devices = []
                
                for i, network_range in enumerate(network_ranges):
                    self.socketio.emit('scan_progress', {
                        'progress': int((i / len(network_ranges)) * 100),
                        'current_range': network_range,
                        'message': f'Scanning {network_range}...'
                    })
                    
                    # Scan this range
                    if self.scanner.detect_wsl2():
                        devices = self.scanner.wsl2_ping_scan(network_range)
                    else:
                        devices = self.scanner.ping_scan(network_range)
                    
                    # Process and save each discovered device
                    for device in devices:
                        if device['mac']:
                            device_id = add_device(
                                mac_address=device['mac'],
                                ip_address=device['ip'],
                                hostname=device['hostname'],
                                vendor=device['vendor']
                            )
                            device['id'] = device_id
                            all_devices.append(device)
                            
                            self.socketio.emit('device_discovered', {
                                'device': device,
                                'total_found': len(all_devices)
                            })
                    
                    if devices:
                        self.socketio.emit('scan_devices_found', {
                            'devices': devices,
                            'range': network_range,
                            'count': len(devices)
                        })
                
                self.socketio.emit('scan_complete', {
                    'message': f'Network scan completed! Found {len(all_devices)} devices.',
                    'devices_found': len(all_devices),
                    'devices': all_devices
                })
                
            except Exception as e:
                print(f"Scan error: {e}")
                self.socketio.emit('scan_error', {'message': f'Scan failed: {str(e)}'})
            finally:
                self.scan_in_progress = False
                
        scan_thread = threading.Thread(target=scan_with_progress)
        scan_thread.daemon = True
        scan_thread.start()

    def get_scan_status(self):
        """Get current scan status"""
        return {
            'scan_in_progress': self.scan_in_progress,
            'monitoring_active': self.monitoring_active
        }

    def force_stop_scan(self):
        """Force stop any running scan"""
        self.scan_in_progress = False
        self.socketio.emit('scan_error', {'message': 'Scan stopped by administrator'})

    def get_monitoring_stats(self):
        """Get monitoring statistics"""
        try:
            conn = get_db_connection()
            
            # Device counts by status
            devices = conn.execute('SELECT * FROM devices').fetchall()
            now = datetime.now()
            status_counts = {'online': 0, 'offline': 0, 'unknown': 0}
            
            for device in devices:
                device_dict = dict(device)
                last_seen_str = device_dict['last_seen']
                
                if last_seen_str:
                    try:
                        last_seen = datetime.fromisoformat(last_seen_str.replace('Z', '+00:00'))
                    except:
                        last_seen = datetime.fromisoformat(last_seen_str)
                else:
                    last_seen = now
                    
                time_diff = (now - last_seen).total_seconds()
                
                if time_diff < 3600:
                    status_counts['online'] += 1
                elif time_diff < 86400:
                    status_counts['unknown'] += 1
                else:
                    status_counts['offline'] += 1
            
            # Recent activity
            recent_devices = conn.execute('''
                SELECT COUNT(*) as count FROM devices 
                WHERE datetime(first_seen) > datetime('now', '-24 hours')
            ''').fetchone()
            
            conn.close()
            
            return {
                'status_counts': status_counts,
                'total_devices': len(devices),
                'devices_discovered_24h': recent_devices['count'],
                'monitoring_active': self.monitoring_active,
                'scan_in_progress': self.scan_in_progress
            }
            
        except Exception as e:
            print(f"Error getting monitoring stats: {e}")
            return {
                'status_counts': {'online': 0, 'offline': 0, 'unknown': 0},
                'total_devices': 0,
                'devices_discovered_24h': 0,
                'monitoring_active': self.monitoring_active,
                'scan_in_progress': self.scan_in_progress
            }