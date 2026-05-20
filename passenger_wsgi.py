"""
WSGI entry point for Phusion Passenger (cPanel, Plesk, DreamHost, etc.).

Passenger loads this module and calls ``application``. Keep this file in the
same directory as the ``app`` package (project root).
"""

import os
import sys

ROOT = os.path.dirname(os.path.abspath(__file__))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

from app import create_app

application = create_app()
