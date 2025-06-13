from .pages import pages_bp
from .devices import devices_bp
from .inventory import inventory_bp
from .categories import categories_bp
from .scanning import scanning_bp
from .dashboard import dashboard_bp

def register_blueprints(app):
    """Register all blueprints with the Flask app"""
    app.register_blueprint(pages_bp)
    app.register_blueprint(devices_bp, url_prefix='/api')
    app.register_blueprint(inventory_bp, url_prefix='/api')
    app.register_blueprint(categories_bp, url_prefix='/api')
    app.register_blueprint(scanning_bp, url_prefix='/api')
    app.register_blueprint(dashboard_bp, url_prefix='/api')