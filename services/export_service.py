# services/export_service.py

import csv
import json
import io
from datetime import datetime
from flask import make_response
from backend.database import get_db_connection

class ExportService:
    """Service for handling inventory data exports"""
    
    @staticmethod
    def export_inventory_csv():
        """Export inventory to CSV format"""
        try:
            conn = get_db_connection()
            inventory = conn.execute('''
                SELECT i.*, d.ip_address, d.mac_address, d.hostname, c.name as category_name
                FROM inventory i
                LEFT JOIN devices d ON i.device_id = d.id
                LEFT JOIN categories c ON i.category_id = c.id
                WHERE i.deleted_at IS NULL
                ORDER BY i.created_at DESC
            ''').fetchall()
            conn.close()
            
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
                    item['category_name'] or item['category'] or '',
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
            
        except Exception as e:
            raise Exception(f"CSV export failed: {str(e)}")

    @staticmethod
    def export_inventory_json():
        """Export inventory to JSON format"""
        try:
            conn = get_db_connection()
            inventory = conn.execute('''
                SELECT i.*, d.ip_address, d.mac_address, d.hostname, c.name as category_name
                FROM inventory i
                LEFT JOIN devices d ON i.device_id = d.id
                LEFT JOIN categories c ON i.category_id = c.id
                WHERE i.deleted_at IS NULL
                ORDER BY i.created_at DESC
            ''').fetchall()
            conn.close()
            
            # Convert to list of dictionaries
            data = []
            for item in inventory:
                data.append({
                    'id': item['id'],
                    'name': item['name'],
                    'category': item['category_name'] or item['category'],
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
                'application': 'HomeTier',
                'version': '1.0.0',
                'inventory': data
            }
            
            response = make_response(json.dumps(export_data, indent=2))
            response.headers['Content-Type'] = 'application/json'
            response.headers['Content-Disposition'] = f'attachment; filename=inventory_export_{datetime.now().strftime("%Y%m%d_%H%M%S")}.json'
            
            return response
            
        except Exception as e:
            raise Exception(f"JSON export failed: {str(e)}")

    @staticmethod
    def export_devices_csv():
        """Export devices to CSV format"""
        try:
            conn = get_db_connection()
            devices = conn.execute('''
                SELECT d.*, i.name as inventory_name, i.category
                FROM devices d
                LEFT JOIN inventory i ON d.id = i.device_id AND i.deleted_at IS NULL
                ORDER BY d.last_seen DESC
            ''').fetchall()
            conn.close()
            
            output = io.StringIO()
            writer = csv.writer(output)
            
            # Write header
            writer.writerow([
                'ID', 'MAC Address', 'IP Address', 'Hostname', 'Vendor', 
                'Device Type', 'First Seen', 'Last Seen', 'Is Monitored', 
                'Is Ignored', 'Inventory Name', 'Category', 'Notes'
            ])
            
            # Write data
            for device in devices:
                writer.writerow([
                    device['id'],
                    device['mac_address'],
                    device['ip_address'] or '',
                    device['hostname'] or '',
                    device['vendor'] or '',
                    device['device_type'] or '',
                    device['first_seen'],
                    device['last_seen'],
                    device['is_monitored'],
                    device['is_ignored'],
                    device['inventory_name'] or '',
                    device['category'] or '',
                    device['notes'] or ''
                ])
            
            output.seek(0)
            
            response = make_response(output.getvalue())
            response.headers['Content-Type'] = 'text/csv'
            response.headers['Content-Disposition'] = f'attachment; filename=devices_export_{datetime.now().strftime("%Y%m%d_%H%M%S")}.csv'
            
            return response
            
        except Exception as e:
            raise Exception(f"Devices CSV export failed: {str(e)}")

    @staticmethod
    def export_combined_report():
        """Export combined inventory and devices report"""
        try:
            conn = get_db_connection()
            
            # Get inventory with device info
            inventory = conn.execute('''
                SELECT 
                    i.*,
                    d.ip_address,
                    d.mac_address,
                    d.hostname,
                    d.vendor,
                    d.first_seen,
                    d.last_seen,
                    c.name as category_name,
                    c.color as category_color,
                    CASE 
                        WHEN i.warranty_expiry IS NULL THEN 'Unknown'
                        WHEN DATE(i.warranty_expiry) < DATE('now') THEN 'Expired'
                        WHEN DATE(i.warranty_expiry) <= DATE('now', '+30 days') THEN 'Expiring Soon'
                        ELSE 'Active'
                    END as warranty_status
                FROM inventory i
                LEFT JOIN devices d ON i.device_id = d.id
                LEFT JOIN categories c ON i.category_id = c.id
                WHERE i.deleted_at IS NULL
                ORDER BY i.created_at DESC
            ''').fetchall()
            
            # Get summary statistics
            stats = conn.execute('''
                SELECT 
                    COUNT(DISTINCT i.id) as total_inventory,
                    COUNT(DISTINCT d.id) as total_devices,
                    COUNT(DISTINCT CASE WHEN d.is_ignored = 0 THEN d.id END) as active_devices,
                    COUNT(DISTINCT CASE WHEN d.is_ignored = 1 THEN d.id END) as ignored_devices,
                    COUNT(DISTINCT CASE WHEN i.warranty_expiry < DATE('now') THEN i.id END) as expired_warranties,
                    COALESCE(SUM(CAST(i.price as REAL)), 0) as total_value
                FROM inventory i
                LEFT JOIN devices d ON i.device_id = d.id
                WHERE i.deleted_at IS NULL
            ''').fetchone()
            
            conn.close()
            
            # Build comprehensive report data
            report_data = {
                'export_date': datetime.now().isoformat(),
                'report_type': 'Combined Inventory and Devices Report',
                'application': 'HomeTier',
                'version': '1.0.0',
                'summary': {
                    'total_inventory_items': stats['total_inventory'],
                    'total_devices_discovered': stats['total_devices'],
                    'active_devices': stats['active_devices'],
                    'ignored_devices': stats['ignored_devices'],
                    'expired_warranties': stats['expired_warranties'],
                    'total_inventory_value': round(stats['total_value'], 2)
                },
                'inventory_items': []
            }
            
            # Add detailed inventory data
            for item in inventory:
                report_data['inventory_items'].append({
                    'id': item['id'],
                    'name': item['name'],
                    'category': item['category_name'] or item['category'],
                    'brand': item['brand'],
                    'model': item['model'],
                    'serial_number': item['serial_number'],
                    'purchase_date': item['purchase_date'],
                    'warranty_expiry': item['warranty_expiry'],
                    'warranty_status': item['warranty_status'],
                    'store_vendor': item['store_vendor'],
                    'price': item['price'],
                    'network_info': {
                        'ip_address': item['ip_address'],
                        'mac_address': item['mac_address'],
                        'hostname': item['hostname'],
                        'vendor': item['vendor'],
                        'first_seen': item['first_seen'],
                        'last_seen': item['last_seen']
                    },
                    'notes': item['notes'],
                    'created_at': item['created_at'],
                    'updated_at': item['updated_at']
                })
            
            response = make_response(json.dumps(report_data, indent=2))
            response.headers['Content-Type'] = 'application/json'
            response.headers['Content-Disposition'] = f'attachment; filename=hometier_report_{datetime.now().strftime("%Y%m%d_%H%M%S")}.json'
            
            return response
            
        except Exception as e:
            raise Exception(f"Combined report export failed: {str(e)}")

    @staticmethod
    def get_export_stats():
        """Get statistics about what can be exported"""
        try:
            conn = get_db_connection()
            
            inventory_count = conn.execute('''
                SELECT COUNT(*) as count FROM inventory WHERE deleted_at IS NULL
            ''').fetchone()['count']
            
            devices_count = conn.execute('''
                SELECT COUNT(*) as count FROM devices
            ''').fetchone()['count']
            
            categories_count = conn.execute('''
                SELECT COUNT(*) as count FROM categories
            ''').fetchone()['count']
            
            total_value = conn.execute('''
                SELECT COALESCE(SUM(CAST(price as REAL)), 0) as total
                FROM inventory WHERE deleted_at IS NULL AND price IS NOT NULL
            ''').fetchone()['total']
            
            conn.close()
            
            return {
                'inventory_items': inventory_count,
                'discovered_devices': devices_count,
                'categories': categories_count,
                'total_inventory_value': round(total_value, 2),
                'export_formats': ['CSV', 'JSON'],
                'available_exports': [
                    'inventory_csv',
                    'inventory_json', 
                    'devices_csv',
                    'combined_report'
                ]
            }
            
        except Exception as e:
            return {
                'error': f"Failed to get export stats: {str(e)}",
                'inventory_items': 0,
                'discovered_devices': 0,
                'categories': 0,
                'total_inventory_value': 0.0
            }