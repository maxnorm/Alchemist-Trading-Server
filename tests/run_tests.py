#!/usr/bin/env python
"""
Simple test runner script
Run this from the project root directory
"""
import sys
import os
import unittest

# Add src to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'src', 'trading_server', 'src'))

if __name__ == '__main__':
    # Discover and run tests
    loader = unittest.TestLoader()
    suite = loader.discover(os.path.dirname(__file__), pattern='test_*.py')
    
    runner = unittest.TextTestRunner(verbosity=2)
    result = runner.run(suite)
    
    # Exit with error code if tests failed
    sys.exit(0 if result.wasSuccessful() else 1)
