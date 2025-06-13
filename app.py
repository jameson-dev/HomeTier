from flask import Flask
from flask_socketio import SocketIO
from backend.database import init_db
from backend.scanner import NetworkScanner
from config import Config
from routes import register_blueprints
from socketio_events import register_socketio_events
from services.realtime_monitor import RealtimeMonitor

# Initialize Flask app
app = Flask(__name__, 
           template_folder='frontend/templates',
           static_folder='frontend/static')
app.config.from_object(Config)

# Initialize SocketIO
socketio = SocketIO(app, cors_allowed_origins="*", async_mode='eventlet')

# Initialize core services
init_db()
scanner = NetworkScanner()
realtime_monitor = RealtimeMonitor(socketio, scanner)

app.scanner = scanner
app.realtime_monitor = realtime_monitor

# Register all routes and events
register_blueprints(app)
register_socketio_events(socketio, realtime_monitor, scanner)

# Error handlers
@app.errorhandler(404)
def not_found_error(error):
    from flask import jsonify
    return jsonify({'status': 'error', 'message': 'Resource not found'}), 404

@app.errorhandler(500)
def internal_error(error):
    from flask import jsonify
    return jsonify({'status': 'error', 'message': 'Internal server error'}), 500

@app.errorhandler(400)
def bad_request_error(error):
    from flask import jsonify
    return jsonify({'status': 'error', 'message': 'Bad request'}), 400

if __name__ == '__main__':
    print("Starting HomeTier Application...")
    print(f"Dashboard: http://{Config.HOST}:{Config.PORT}")
    print(f"Real-time features: {'Enabled' if socketio else 'Disabled'}")
    print(f"Debug mode: {'On' if Config.DEBUG else 'Off'}")
    print("Async mode: eventlet")
    
    socketio.run(
        app, 
        host=Config.HOST, 
        port=Config.PORT, 
        debug=Config.DEBUG
    )