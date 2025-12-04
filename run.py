#!/usr/bin/env python3
"""
Application entry point with Windows protection features.
"""

import sys
import os

# Add project root to path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

# Try to protect the process on Windows
try:
    from windows_admin import is_admin, request_admin
    if sys.platform == 'win32':
        if not is_admin():
            request_admin()
except ImportError:
    pass

# Import and run the main application
from monitoring_app import main

if __name__ == "__main__":
    main()
