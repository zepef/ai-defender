#!/usr/bin/env python3
"""
Wrapper for hexstrike_mcp.py that increases the health check timeout.

The upstream hexstrike_mcp.py uses a 5s timeout for health checks during init,
which is too short when the Flask server is checking 127+ tools via subprocess.
This wrapper patches the timeout before starting.
"""
import sys
import os

# Add hexstrike-ai directory to path
script_dir = os.path.dirname(os.path.abspath(__file__))
hexstrike_dir = os.path.join(script_dir, "hexstrike-ai")
sys.path.insert(0, hexstrike_dir)
os.chdir(hexstrike_dir)

# Patch requests.Session.get to use a longer timeout for health checks
import requests

_original_get = requests.Session.get

def _patched_get(self, url, **kwargs):
    if "/health" in str(url) and kwargs.get("timeout", 0) <= 5:
        kwargs["timeout"] = 30
    return _original_get(self, url, **kwargs)

requests.Session.get = _patched_get

# Now run hexstrike_mcp main
from hexstrike_mcp import main
main()
