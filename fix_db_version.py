
from app import create_app, db
from sqlalchemy import text

app = create_app()

with app.app_context():
    print("Checking current alembic_version...")
    try:
        current_version = db.session.execute(text("SELECT version_num FROM alembic_version")).scalar()
        print(f"Current version in DB: {current_version}")
    except Exception as e:
        print(f"Error checking version: {e}")

    target_version = '95107be9594c'
    print(f"Forcing version to: {target_version}")
    
    try:
        # Check if table has rows
        count = db.session.execute(text("SELECT count(*) FROM alembic_version")).scalar()
        if count == 0:
            db.session.execute(text("INSERT INTO alembic_version (version_num) VALUES (:v)"), {'v': target_version})
        else:
            db.session.execute(text("UPDATE alembic_version SET version_num = :v"), {'v': target_version})
        
        db.session.commit()
        print("Successfully updated alembic_version.")
        
        # Verify
        new_version = db.session.execute(text("SELECT version_num FROM alembic_version")).scalar()
        print(f"New version in DB: {new_version}")

    except Exception as e:
        db.session.rollback()
        print(f"Failed to update version: {e}")
