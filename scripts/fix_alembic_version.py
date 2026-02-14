from app import create_app, db
from sqlalchemy import text

app = create_app()
with app.app_context():
    try:
        # Check current version
        result = db.session.execute(text("SELECT version_num FROM alembic_version")).fetchone()
        print(f"Current version: {result[0] if result else 'None'}")
        
        # Update version
        db.session.execute(text("DELETE FROM alembic_version"))
        db.session.execute(text("INSERT INTO alembic_version (version_num) VALUES ('95107be9594c')"))
        db.session.commit()
        print("Fixed alembic_version to 95107be9594c")
    except Exception as e:
        print(f"Error: {e}")
        db.session.rollback()
