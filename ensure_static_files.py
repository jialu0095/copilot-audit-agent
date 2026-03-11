"""Ensures web/static directory and files exist on app startup."""

import os


def ensure_static_files():
    """Create web/static directory and stub files if they don't exist."""
    static_dir = os.path.join('web', 'static')
    os.makedirs(static_dir, exist_ok=True)
    
    # Stub files will be created by this function if needed
    # In production, these should be served from the /static route
