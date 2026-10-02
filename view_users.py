from app import app
from models import User

with app.app_context():
    users = User.query.all()
    print(f"\n--- Total Users: {len(users)} ---")
    for user in users:
        print(f"Name: {user.name} | Email: {user.email}")
    print("----------------------\n")
