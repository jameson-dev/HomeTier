from .scanning import register_scanning_events
from .monitoring import register_monitoring_events

def register_socketio_events(socketio, realtime_monitor, scanner):
    """Register all SocketIO event handlers"""
    register_scanning_events(socketio, realtime_monitor, scanner)
    register_monitoring_events(socketio, realtime_monitor)