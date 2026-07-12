import socket

from app import create_app

app = create_app()


def get_lan_ip():
    try:
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        s.connect(("8.8.8.8", 80))
        ip = s.getsockname()[0]
        s.close()
        return ip
    except OSError:
        return "127.0.0.1"


if __name__ == "__main__":
    lan_ip = get_lan_ip()
    print("\n" + "=" * 50)
    print("  SKSS-MIS - Supermarket Management System")
    print("=" * 50)
    print(f"  Local:   http://127.0.0.1:5000")
    print(f"  LAN:     http://{lan_ip}:5000")
    print("  Default login: admin / admin123")
    print("=" * 50 + "\n")
    app.run(host="0.0.0.0", port=5000, debug=False)
