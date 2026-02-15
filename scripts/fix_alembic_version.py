import sys
import os
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app import create_app, db
from sqlalchemy import text

def fix_version():
    app = create_app()
    with app.app_context():
        try:
            # Check current version
            result = db.session.execute(text("SELECT version_num FROM alembic_version"))
            row = result.fetchone()
            current = row[0] if row else "None"
            print(f"Current version in DB: {current}")
            
            # Update to known head 'f5bf397b9d45'
            target = 'f5bf397b9d45'
            print(f"Forcing version to: {target}")
            
            if row:
                db.session.execute(text("UPDATE alembic_version SET version_num = :v"), {'v': target})
            else:
                db.session.execute(text("INSERT INTO alembic_version (version_num) VALUES (:v)"), {'v': target})
                
            db.session.commit()
            print("Successfully updated alembic_version.")
        except Exception as e:
            print(f"Error: {e}")
            sys.exit(1)

if __name__ == "__main__":
    fix_version()
