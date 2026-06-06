from app import create_app, db
import sqlalchemy
from sqlalchemy.schema import CreateTable
from app.models import HallPassSettings

app = create_app()
with app.app_context():
    print(CreateTable(HallPassSettings.__table__).compile(db.engine))
