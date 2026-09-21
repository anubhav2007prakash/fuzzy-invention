"""Database engine, session factory and table initialisation.

Table creation strategy:
  - If Alembic has been set up and migrations exist, run ``alembic upgrade head``.
  - Otherwise, fall back to ``Base.metadata.create_all()`` for development.
"""
import logging
from pathlib import Path
from sqlalchemy import create_engine
from sqlalchemy.orm import DeclarativeBase, sessionmaker
from backend.app.core.config import settings

logger = logging.getLogger(__name__)


class Base(DeclarativeBase):
    pass


engine = create_engine(
    settings.DATABASE_URL,
    connect_args={"check_same_thread": False}
    if settings.DATABASE_URL.startswith("sqlite")
    else {},
    echo=False,
)

SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)


def get_db():
    """FastAPI dependency — yields a SQLAlchemy session."""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def _run_alembic_migrations() -> bool:
    """Attempt to run Alembic migrations. Returns True on success."""
    try:
        from alembic.config import Config
        from alembic import command
        # Look for alembic.ini relative to the project root
        alembic_cfg_path = Path(__file__).resolve().parents[3] / "alembic.ini"
        if not alembic_cfg_path.exists():
            return False
        cfg = Config(str(alembic_cfg_path))
        command.upgrade(cfg, "head")
        logger.info("Alembic migrations applied successfully.")
        return True
    except Exception as exc:
        logger.warning("Alembic migration failed (%s), falling back to create_all.", exc)
        return False


def init_db() -> None:
    """Create all tables if they do not exist (called on startup).

    Strategy:
      1. Try Alembic migrations first (recommended for production).
      2. Fall back to Base.metadata.create_all() for development.
    """
    # Import all ORM models so SQLAlchemy sees them before create_all
    import backend.app.db.models  # noqa: F401  # registers all mappers

    if not _run_alembic_migrations():
        logger.info("Using create_all() for table initialization.")
        Base.metadata.create_all(bind=engine)
