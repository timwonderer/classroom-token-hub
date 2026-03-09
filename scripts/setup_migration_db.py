import os
import sys
from pathlib import Path

from alembic import command
from alembic.config import Config
from alembic.script import ScriptDirectory


PROJECT_ROOT = Path(__file__).resolve().parent.parent
ALEMBIC_INI = PROJECT_ROOT / "migrations" / "alembic.ini"


def _get_alembic_config() -> Config:
    config = Config(str(ALEMBIC_INI))
    config.set_main_option("script_location", str(PROJECT_ROOT / "migrations"))
    config.set_main_option("sqlalchemy.url", os.environ["DATABASE_URL"])
    return config


def main() -> None:
    config = _get_alembic_config()
    script = ScriptDirectory.from_config(config)
    head = script.get_current_head()

    print(f"Applying Alembic migrations to head: {head}")
    command.upgrade(config, "head")
    print("Database schema is now at Alembic head.")


if __name__ == "__main__":
    try:
        main()
    except Exception as exc:
        print(f"Failed to initialize database: {exc}", file=sys.stderr)
        raise
