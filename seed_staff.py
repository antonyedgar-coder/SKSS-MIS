"""Create a staff user. Usage: python seed_staff.py [username] [password]"""
import sys

from app import create_app
from app.extensions import db
from app.models import User

app = create_app()

with app.app_context():
    username = sys.argv[1] if len(sys.argv) > 1 else "staff"
    password = sys.argv[2] if len(sys.argv) > 2 else "staff123"

    if User.query.filter_by(username=username).first():
        print(f"User '{username}' already exists.")
    else:
        user = User(username=username, role="staff")
        user.set_password(password)
        db.session.add(user)
        db.session.commit()
        print(f"Staff user created: {username} / {password}")
