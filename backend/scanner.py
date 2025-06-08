import scapy.all as scapy
import nmap
import socket
import subprocess
import re
from datetime import datetime
from backend.database import add_device, get_db_connection
from config import Config
import threading
import time

class NetworkScanner:
    def __init__(self):
        self.nm = nmap.PortScanner()
        self.vendor_db = self._load_vendor_db()
        
    def _load_vendor_db(self):
        """Load MAC vendor database from IEEE OUI"""
        import requests
        import os
        from pathlib import Path
        
        vendor_db = {}
        oui_file = Path('data/oui.txt')
        
        try:
            print(f"DEBUG: File exists: {oui_file.exists()}")
            if oui_file.exists():
                file_age = time.time() - oui_file.stat().st_mtime
                cache_valid = file_age < (30 * 24 * 3600)
                print(f"DEBUG: File age: {file_age/3600:.1f} hours, Cache valid: {cache_valid}")
            
            # Check if we have a cached OUI file less than 30 days old
            if oui_file.exists() and (time.time() - oui_file.stat().st_mtime) < (30 * 24 * 3600):
                print("Loading cached OUI database...")
                with open(oui_file, 'r', encoding='utf-8', errors='ignore') as f:
                    content = f.read()
                print(f"DEBUG: Read {len(content)} characters from cache")
            else:
                print("Downloading IEEE OUI database...")
                # Download the latest OUI database
                headers = {
                    'User-Agent': 'Mozilla/5.0 (Linux; x86_64) AppleWebKit/537.36 Network Inventory Manager',
                    'Accept': 'text/plain',
                }
                response = requests.get(
                    'https://standards-oui.ieee.org/oui/oui.txt',
                    headers=headers,
                    timeout=30
                )
                response.raise_for_status()
                content = response.text
                
                # Cache the downloaded file
                os.makedirs('data', exist_ok=True)
                with open(oui_file, 'w', encoding='utf-8') as f:
                    f.write(content)
                print("OUI database downloaded and cached")
            
                print("DEBUG: Starting to parse content...")
                lines_processed = 0
                hex_lines = 0
                
                # Parse the OUI file
                for line in content.splitlines():
                    lines_processed += 1
                    if '(hex)' in line:
                        hex_lines += 1
                        parts = line.split('\t')
                        if len(parts) >= 3:
                            oui_hex = parts[0].strip().replace('-', ':').lower()
                            oui_hex = oui_hex.replace('(hex)', '').strip()
                            company = parts[2].strip()
                            if company:
                                vendor_db[oui_hex] = company
                
                print(f"DEBUG: Processed {lines_processed} lines, {hex_lines} with (hex), {len(vendor_db)} entries added")
                print(f"Loaded {len(vendor_db)} vendor entries from IEEE OUI database")
                
        except Exception as e:
            print(f"Error loading IEEE OUI database: {e}")
            import traceback
            traceback.print_exc()
            # Fallback to basic database if download fails
            vendor_db = {
                '00:50:56': 'VMware',
                '08:00:27': 'VirtualBox', 
                '52:54:00': 'QEMU',
                'b8:27:eb': 'Raspberry Pi Foundation',
                'dc:a6:32': 'Raspberry Pi Foundation',
                'e4:5f:01': 'Raspberry Pi Foundation',
                '00:16:3e': 'Xen',
                '00:1b:21': 'Intel Corporate',
                '00:1e:58': 'WistronInfocomm',
                '00:26:b9': 'Seagate Technology',
                '28:c6:8e': 'Ubiquiti Networks',
                '00:0c:29': 'VMware',
                '00:15:5d': 'Microsoft Corporation',
                '00:1c:42': 'Parallels',
                '00:03:ff': 'Microsoft Corporation',
                '00:50:f2': 'Microsoft Corporation',
                '00:17:fa': 'Honeywell',
                '70:b3:d5': 'IEEE Registration Authority',
                'ac:de:48': 'Private',
                '02:00:00': 'Locally Administered'
            }
        print(f"DEBUG: Returning {len(vendor_db)} entries")
        return vendor_db
    
    def detect_wsl2(self):
        """Detect if running in WSL2 environment"""
        try:
            with open('/proc/version', 'r') as f:
                return 'microsoft' in f.read().lower()
        except:
            return False
    
    def get_network_range(self):
        """Auto-detect local network range"""
        try:
            # Get default gateway
            result = subprocess.run(['ip', 'route', 'show', 'default'], 
                                  capture_output=True, text=True)
            if result.returncode == 0:
                # Extract gateway IP
                gateway_match = re.search(r'via (\d+\.\d+\.\d+\.\d+)', result.stdout)
                if gateway_match:
                    gateway = gateway_match.group(1)
                    # Assume /24 network
                    network_base = '.'.join(gateway.split('.')[:-1])
                    return f"{network_base}.0/24"
        except Exception as e:
            print(f"Error detecting network range: {e}")
        
        return Config.NETWORK_RANGE
    
    def get_vendor_from_mac(self, mac_address):
        """Get vendor from MAC address"""
        if not mac_address:
            return None
            
        # Get first 3 octets
        mac_prefix = ':'.join(mac_address.split(':')[:3]).lower()
        return self.vendor_db.get(mac_prefix, 'Unknown')
    
    def get_mac_for_ip(self, ip):
        """Try to get MAC address for IP"""
        # Try ping then check ARP table
        try:
            subprocess.run(['ping', '-c', '1', '-W', '1', ip], 
                          capture_output=True, timeout=3)
            result = subprocess.run(['arp', '-n'], capture_output=True, text=True)
            for line in result.stdout.splitlines():
                if ip in line:
                    parts = line.split()
                    if len(parts) >= 3:
                        mac = parts[2] if len(parts[2]) == 17 else parts[1]
                        if ':' in mac and len(mac) == 17:
                            return mac
        except:
            pass
        
        return None
    
    def wsl2_ping_scan(self, network_range):
        """Use nmap for WSL2 since ARP table is isolated"""
        try:
            print(f"WSL2 detected - using nmap scan for {network_range}")
            self.nm.scan(hosts=network_range, arguments='-sn --host-timeout 2s')
            
            devices = []
            for host in self.nm.all_hosts():
                if self.nm[host].state() == 'up':
                    device = {
                        'ip': host,
                        'mac': self.get_mac_for_ip(host),
                        'hostname': self.get_hostname(host),
                        'vendor': None
                    }
                    if device['mac']:
                        device['vendor'] = self.get_vendor_from_mac(device['mac'])
                        devices.append(device)
                        
            return devices
            
        except Exception as e:
            print(f"WSL2 scan failed: {e}")
            return []
    
    def ping_scan(self, network_range=None):
        """Perform ping scan using host system's network stack"""
        if network_range is None:
            network_range = self.get_network_range()
            
        print(f"Scanning network range: {network_range}")
        
        try:
            # Use nmap first to populate ARP table, then read host ARP
            print("Using nmap + host ARP method for Ubuntu...")
            
            # Step 1: Use nmap to discover live hosts
            self.nm.scan(hosts=network_range, arguments='-sn --host-timeout 2s')
            
            # Step 2: Read ARP table from host system (works even in container)
            devices = []
            live_ips = [host for host in self.nm.all_hosts() if self.nm[host].state() == 'up']
            
            for ip in live_ips:
                # Try to get MAC from multiple sources
                mac = self.get_mac_from_proc(ip) or self.get_mac_for_ip(ip)
                
                if mac:
                    device = {
                        'ip': ip,
                        'mac': mac,
                        'hostname': self.get_hostname(ip),
                        'vendor': self.get_vendor_from_mac(mac)
                    }
                    devices.append(device)
                    
            return devices
            
        except Exception as e:
            print(f"Error during scan: {e}")
            return []

    def get_mac_from_proc(self, ip):
        """Try to get MAC from /proc/net/arp (often works in containers)"""
        try:
            with open('/proc/net/arp', 'r') as f:
                for line in f:
                    parts = line.split()
                    if len(parts) >= 4 and parts[0] == ip:
                        mac = parts[3]
                        if mac != "00:00:00:00:00:00" and ":" in mac:
                            return mac.lower()
        except:
            pass
        return None
    
    def fallback_scan(self, network_range):
        """Fallback scan using nmap if scapy fails"""
        try:
            print("Using nmap fallback scan...")
            self.nm.scan(hosts=network_range, arguments='-sn')
            
            devices = []
            for host in self.nm.all_hosts():
                if self.nm[host].state() == 'up':
                    # Try to get MAC address
                    mac = None
                    if 'mac' in self.nm[host]['addresses']:
                        mac = self.nm[host]['addresses']['mac']
                    
                    device = {
                        'ip': host,
                        'mac': mac,
                        'hostname': self.get_hostname(host),
                        'vendor': self.get_vendor_from_mac(mac) if mac else None
                    }
                    devices.append(device)
                    
            return devices
            
        except Exception as e:
            print(f"Fallback scan failed: {e}")
            return []
    
    def get_hostname(self, ip_address):
        """Get hostname from IP address using multiple methods"""
        # Method 1: Standard reverse DNS lookup
        try:
            hostname = socket.gethostbyaddr(ip_address)[0]
            if hostname and not hostname.startswith(ip_address):
                return hostname.split('.')[0]  # Return just the host part
        except (socket.herror, socket.gaierror):
            pass
        
        # Method 2: Try nslookup command
        try:
            result = subprocess.run(['nslookup', ip_address], 
                                capture_output=True, text=True, timeout=3)
            for line in result.stdout.splitlines():
                if 'name =' in line.lower():
                    hostname = line.split('=')[1].strip().rstrip('.')
                    return hostname.split('.')[0]
        except:
            pass
        
        # Method 3: Try netbios/SMB name (for Windows devices)
        try:
            result = subprocess.run(['nmblookup', '-A', ip_address], 
                                capture_output=True, text=True, timeout=3)
            for line in result.stdout.splitlines():
                if '<00>' in line and 'GROUP' not in line:
                    hostname = line.split()[0].strip()
                    if hostname and hostname != '*':
                        return hostname
        except:
            pass
        
        return None
    
    def scan_network(self):
        """Main network scanning function"""
        print(f"Starting network scan at {datetime.now()}")
        
        network_range = self.get_network_range()
        
        # Try multiple methods for Ubuntu
        devices = self.ping_scan(network_range)
        
        if not devices:
            print("Trying netlink method...")
            devices = self.netlink_scan(network_range)
        
        # Process discovered devices
        processed_devices = []
        for device in devices:
            if device['mac']:  # Only process devices with MAC addresses
                device_id = add_device(
                    mac_address=device['mac'],
                    ip_address=device['ip'],
                    hostname=device['hostname'],
                    vendor=device['vendor']
                )
                
                device['id'] = device_id
                processed_devices.append(device)
                
        print(f"Scan completed. Found {len(processed_devices)} devices with MAC addresses")
        return processed_devices
    
    def start_periodic_scan(self, interval=None):
        """Start periodic network scanning"""
        if interval is None:
            interval = Config.SCAN_INTERVAL
            
        def scan_loop():
            while True:
                try:
                    self.scan_network()
                    time.sleep(interval)
                except Exception as e:
                    print(f"Error in periodic scan: {e}")
                    time.sleep(60)  # Wait 1 minute before retrying
                    
        scan_thread = threading.Thread(target=scan_loop, daemon=True)
        scan_thread.start()
        return scan_thread

# Utility functions for database operations
def mark_device_ignored(device_id):
    """Mark a device as ignored"""
    conn = get_db_connection()
    conn.execute('UPDATE devices SET is_ignored = 1 WHERE id = ?', (device_id,))
    conn.commit()
    conn.close()

def add_to_inventory(device_id, name, category=None, **kwargs):
    """Add device to managed inventory"""
    conn = get_db_connection()
    
    fields = ['device_id', 'name']
    values = [device_id, name]
    placeholders = ['?', '?']
    
    if category:
        fields.append('category')
        values.append(category)
        placeholders.append('?')
    
    # Add optional fields
    optional_fields = ['brand', 'model', 'purchase_date', 'warranty_expiry', 
                      'store_vendor', 'price', 'serial_number', 'notes']
    
    for field in optional_fields:
        if field in kwargs and kwargs[field]:
            fields.append(field)
            values.append(kwargs[field])
            placeholders.append('?')
    
    query = f'''
        INSERT INTO inventory ({', '.join(fields)})
        VALUES ({', '.join(placeholders)})
    '''
    
    cursor = conn.execute(query, values)
    inventory_id = cursor.lastrowid
    conn.commit()
    conn.close()
    
    return inventory_id