"""WSGI adapter for PythonAnywhere."""

from a2wsgi import ASGIMiddleware

from pythonanywhere_app import app

# PythonAnywhere WSGI file should expose this variable.
application = ASGIMiddleware(app)
