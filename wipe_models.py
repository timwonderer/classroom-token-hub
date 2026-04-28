with open("app/models.py", "w") as f:
    f.write('from app.extensions import db\nfrom sqlalchemy.dialects.postgresql import JSONB, UUID\nfrom datetime import datetime\nimport uuid\n')
