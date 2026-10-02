"""
StudyAI Database Reset Utility
Use this script to completely wipe and recreate fresh, empty tables in the active database.
Works seamlessly for both local SQLite and Render PostgreSQL.
"""
import sys
from app import app, db

def reset_database():
    with app.app_context():
        print(f"Target Database: {app.config['SQLALCHEMY_DATABASE_URI']}")
        print("Dropping all existing tables...")
        db.drop_all()
        print("Recreating fresh database schema...")
        db.create_all()
        print("[SUCCESS] All tables have been wiped and recreated completely fresh (0 users, 0 subjects, 0 tasks, 0 progress)!")

if __name__ == "__main__":
    confirm = input("Are you sure you want to permanently delete ALL data? (yes/no): ") if len(sys.argv) == 1 else "yes"
    if confirm.strip().lower() in ['y', 'yes']:
        reset_database()
    else:
        print("Database reset cancelled.")
