#!/usr/bin/env python
"""
Run script for the account service.
Usage: pipenv run python run.py
"""
import sys
import os
import uvicorn

# Add the current directory to the Python path to allow imports
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

if __name__ == "__main__":
    uvicorn.run("app.main:app", host="0.0.0.0", port=8000, reload=False)