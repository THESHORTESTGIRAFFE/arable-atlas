import os
import sys
import socket
import subprocess
from app import app
from waitress import serve

def get_local_ip():
    try:
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        s.connect(("8.8.8.8", 80))
        ip = s.getsockname()[0]
        s.close()
        return ip
    except Exception:
        try:
            return socket.gethostbyname(socket.gethostname())
        except Exception:
            return "127.0.0.1"

def find_free_port(start_port=8080):
    port = start_port
    while port < 65535:
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
            try:
                s.bind(('0.0.0.0', port))
                return port
            except OSError:
                port += 1
    raise RuntimeError("No free ports found.")

def main():
    from dotenv import load_dotenv
    load_dotenv()

    # Determine port
    default_port = int(os.environ.get("PORT", 8080))
    try:
        port = find_free_port(default_port)
    except Exception as e:
        print(f"Error finding a free port: {e}")
        sys.exit(1)

    local_ip = get_local_ip()

    # ASCII banner
    emmorphique_banner = """
    ███████╗███╗   ███╗███╗   ███╗ ██████╗ ██████╗ ██████╗ ██╗  ██╗██╗ ██████╗
    ██╔════╝████╗ ████║████╗ ████║██╔═══██╗██╔══██╗██╔══██╗██║  ██║██║██╔════╝
    █████╗  ██╔████╔██║██╔████╔██║██║   ██║██████╔╝██████╔╝███████║██║██║     
    ██╔══╝  ██║╚██╔╝██║██║╚██╔╝██║██║   ██║██╔══██╗██╔═══╝ ██╔══██║██║██║     
    ███████╗██║ ╚═╝ ██║██║ ╚═╝ ██║╚██████╔╝██║  ██║██║     ██║  ██║██║╚██████╗
    ╚══════╝╚═╝     ╚═╝╚═╝     ╚═╝ ╚═════╝ ╚═╝  ╚═╝╚═╝     ╚═╝  ╚═╝╚═╝ ╚═════╝
                                                                             
    Project   : Arable Atlas
    Developer : EMMORPHIC
    Status    : Production
"""
    banner = f"""
============================================================
🌱  ARABLE ATLAS - PRODUCTION SERVER
============================================================
Status:          RUNNING (via Waitress WSGI)
Local Access:    http://localhost:{port}
Network Access:  http://{local_ip}:{port}
============================================================
👉 Press Ctrl+C to shut down the server.
============================================================
"""
    print(emmorphique_banner)
    print(banner)

    try:
        serve(app, host='0.0.0.0', port=port, threads=4)
    except KeyboardInterrupt:
        print("\nStopping Arable Atlas server. Goodbye!")

if __name__ == '__main__':
    main()
