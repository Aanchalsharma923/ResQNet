# Pytest configuration
import sys
import os

# Ensure the root directory is in the sys.path so tests can import from resqnet
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))
