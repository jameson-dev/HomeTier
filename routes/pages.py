from flask import Blueprint, render_template

pages_bp = Blueprint('pages', __name__)

@pages_bp.route('/')
def index():
    return render_template('index.html')

@pages_bp.route('/inventory')
def inventory():
    return render_template('inventory.html')

@pages_bp.route('/scanning')
def scanning():
    return render_template('scanning.html')

@pages_bp.route('/categories')
def categories():
    return render_template('categories.html')