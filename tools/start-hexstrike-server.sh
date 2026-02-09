#!/usr/bin/env bash
# Start HexStrike AI Flask server with threading enabled
# This wrapper ensures concurrent request handling (health checks don't block tool execution)

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
HEXSTRIKE_DIR="$SCRIPT_DIR/hexstrike-ai"
VENV_PYTHON="$HEXSTRIKE_DIR/.venv/bin/python3"

if [[ ! -f "$VENV_PYTHON" ]]; then
    echo "Error: HexStrike venv not found at $VENV_PYTHON"
    echo "Run: cd $HEXSTRIKE_DIR && uv venv .venv && uv pip install -r requirements.txt"
    exit 1
fi

cd "$HEXSTRIKE_DIR"
exec "$VENV_PYTHON" -c "
import sys, os
os.chdir('$HEXSTRIKE_DIR')
sys.argv = ['hexstrike_server.py']

# Patch Flask's app.run to enable threading before the module runs
import flask
_original_run = flask.Flask.run
def _threaded_run(self, *args, **kwargs):
    kwargs['threaded'] = True
    return _original_run(self, *args, **kwargs)
flask.Flask.run = _threaded_run

# Now run the server as __main__
sys.argv = ['hexstrike_server.py']
exec(open('hexstrike_server.py').read())
"
