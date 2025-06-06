"""
HomeTier Backend

This package contains the core backend functionality for the HomeTier,
including database operations, network scanning, and device management.
"""

from .database import init_db, get_db_connection, add_device
from .scanner import NetworkScanner

__version__ = "1.0.0"
__all__ = ["init_db", "get_db_connection", "add_device", "NetworkScanner"]