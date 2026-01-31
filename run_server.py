#!/usr/bin/env python3
"""
Run the Kuiper TTS API server.

Usage:
    python run_server.py [--port PORT] [--reload]
"""

import sys
import argparse
import socket
from pathlib import Path

# Add the project root to Python path
project_root = Path(__file__).parent.resolve()
sys.path.insert(0, str(project_root))
sys.path.insert(0, str(project_root / "backend"))


def find_available_port(start_port: int, max_attempts: int = 10) -> int:
    """Find an available port starting from start_port."""
    for i in range(max_attempts):
        port = start_port + i
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
            try:
                s.bind(('127.0.0.1', port))
                return port
            except OSError:
                continue
    raise RuntimeError(f"Could not find an available port starting from {start_port}")


def main():
    parser = argparse.ArgumentParser(description="Run Kuiper TTS API server")
    parser.add_argument("--port", type=int, default=None, help="Port to run on (overrides env/config)")
    parser.add_argument("--host", default=None, help="Host to bind to (overrides env/config)")
    parser.add_argument("--reload", action="store_true", help="Enable auto-reload")
    parser.add_argument("--auto-port", action="store_true", default=True, help="Automatically find available port if default is in use")
    args = parser.parse_args()

    try:
        import uvicorn
        from backend.core.config import get_settings
    except ImportError as e:
        print(f"Error: Required package not installed: {e}")
        print("Run: pip install -r backend/requirements.txt")
        sys.exit(1)

    # Load settings
    settings = get_settings()
    
    # Use command line args if provided, otherwise use settings
    host = args.host if args.host is not None else settings.host
    port = args.port if args.port is not None else settings.port
    reload = args.reload or settings.reload

    # Check if port is available, find another if needed
    if args.auto_port:
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
            try:
                s.bind((host, port))
            except OSError:
                print(f"Port {port} is already in use, finding an available port...")
                port = find_available_port(port)
                print(f"Using port {port} instead")

    print(f"Starting Kuiper TTS API server on http://{host}:{port}")
    print(f"Environment: {settings.environment}")
    print("Press Ctrl+C to stop")
    
    uvicorn.run(
        "backend.api.main:app",
        host=host,
        port=port,
        reload=reload,
    )


if __name__ == "__main__":
    main()

