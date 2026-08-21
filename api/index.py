import sys
import os

# Menambahkan root direktori ke path pencarian modul Python
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app import app
