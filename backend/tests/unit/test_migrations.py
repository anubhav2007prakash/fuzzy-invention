"""Tests for Alembic database migration integrity.

Verifies:
1. Upgrade from an empty database to current schema succeeds.
2. The generated migration matches ORM models (no missing/extra tables, correct columns).
3. Downgrade then re-upgrade produces a consistent schema.
"""
import os
import subprocess
import sys
import tempfile
import unittest

from alembic.config import Config
from alembic import command
from sqlalchemy import create_engine, inspect, text

from backend.app.db.database import Base

# Import all ORM models so Base.metadata is populated
import backend.app.db.models  # noqa: F401


def _get_alembic_cfg(db_url: str) -> Config:
    """Create an Alembic Config pointing at the given database URL."""
    cfg = Config("alembic.ini")
    cfg.set_main_option("sqlalchemy.url", db_url)
    return cfg


def _get_expected_tables() -> set[str]:
    """Return the set of table names defined by ORM models (excluding alembic_version)."""
    return set(Base.metadata.tables.keys())


def _get_expected_columns(table_name: str) -> dict[str, str]:
    """Return {column_name: type_string} for a given ORM table."""
    table = Base.metadata.tables[table_name]
    return {col.name: str(col.type) for col in table.columns}


def _get_expected_indexes() -> dict[str, dict]:
    """Return {index_name: {table, unique, columns}} for all ORM-defined indexes."""
    result = {}
    for table in Base.metadata.sorted_tables:
        for idx in table.indexes:
            result[idx.name] = {
                "table": table.name,
                "unique": idx.unique,
                "columns": sorted(c.name for c in idx.columns),
            }
    # Also include unique constraints that act as indexes
    for table in Base.metadata.sorted_tables:
        for uq in table.constraints:
            if hasattr(uq, "column_names") and uq.column_names:
                # UniqueConstraint creates an implicit index in SQLite
                pass
    return result


class TestMigrationUpgrade(unittest.TestCase):
    """Test 1: Upgrade from empty database to current schema succeeds."""

    def setUp(self):
        self.tmpdir = tempfile.mkdtemp()
        self.db_path = os.path.join(self.tmpdir, "test_upgrade.db")
        self.db_url = f"sqlite:///{self.db_path}"
        self.engine = create_engine(self.db_url)

    def tearDown(self):
        self.engine.dispose()
        # Clean up temp files
        for f in os.listdir(self.tmpdir):
            os.remove(os.path.join(self.tmpdir, f))
        os.rmdir(self.tmpdir)

    def test_upgrade_creates_all_tables(self):
        """Running upgrade head on an empty DB should create all ORM tables."""
        cfg = _get_alembic_cfg(self.db_url)
        command.upgrade(cfg, "head")

        inspector = inspect(self.engine)
        actual_tables = set(inspector.get_table_names()) - {"alembic_version"}
        expected_tables = _get_expected_tables()

        self.assertEqual(actual_tables, expected_tables,
                         f"Missing tables: {expected_tables - actual_tables}\n"
                         f"Extra tables: {actual_tables - expected_tables}")

    def test_upgrade_creates_all_indexes(self):
        """Running upgrade head should create all ORM-defined indexes."""
        cfg = _get_alembic_cfg(self.db_url)
        command.upgrade(cfg, "head")

        inspector = inspect(self.engine)
        expected_indexes = _get_expected_indexes()

        for idx_name, idx_info in expected_indexes.items():
            table_name = idx_info["table"]
            table_indexes = {i["name"]: i for i in inspector.get_indexes(table_name)}
            self.assertIn(idx_name, table_indexes,
                          f"Index '{idx_name}' missing from table '{table_name}'")

    def test_upgrade_stamps_alembic_version(self):
        """After upgrade, alembic_version should record the current revision."""
        cfg = _get_alembic_cfg(self.db_url)
        command.upgrade(cfg, "head")

        with self.engine.connect() as conn:
            result = conn.execute(text("SELECT version_num FROM alembic_version"))
            versions = [r[0] for r in result]

        self.assertEqual(len(versions), 1)
        self.assertEqual(versions[0], "0003_lineage")


class TestMigrationSchemaMatch(unittest.TestCase):
    """Test 2: Verify migration produces a schema matching ORM models exactly."""

    def setUp(self):
        self.tmpdir = tempfile.mkdtemp()
        self.db_path = os.path.join(self.tmpdir, "test_schema.db")
        self.db_url = f"sqlite:///{self.db_path}"
        self.engine = create_engine(self.db_url)

        # Run migration
        cfg = _get_alembic_cfg(self.db_url)
        command.upgrade(cfg, "head")
        self.inspector = inspect(self.engine)

    def tearDown(self):
        self.engine.dispose()
        for f in os.listdir(self.tmpdir):
            os.remove(os.path.join(self.tmpdir, f))
        os.rmdir(self.tmpdir)

    def test_no_missing_tables(self):
        """Every ORM-defined table must exist after migration."""
        actual = set(self.inspector.get_table_names()) - {"alembic_version"}
        expected = _get_expected_tables()
        missing = expected - actual
        self.assertEqual(missing, set(), f"Tables missing from migration: {missing}")

    def test_no_extra_tables(self):
        """No tables should exist beyond what ORM models define."""
        actual = set(self.inspector.get_table_names()) - {"alembic_version"}
        expected = _get_expected_tables()
        extra = actual - expected
        self.assertEqual(extra, set(), f"Unexpected tables in migration: {extra}")

    def test_column_names_match_per_table(self):
        """Each table's column names must match the ORM definition."""
        for table_name in _get_expected_tables():
            expected_cols = set(_get_expected_columns(table_name).keys())
            actual_cols = {col["name"] for col in self.inspector.get_columns(table_name)}
            self.assertEqual(actual_cols, expected_cols,
                             f"Column mismatch on '{table_name}':\n"
                             f"  Missing from DB: {expected_cols - actual_cols}\n"
                             f"  Extra in DB: {actual_cols - expected_cols}")

    def test_foreign_keys_present(self):
        """Foreign key relationships defined in ORM must exist in DB."""
        for table_name in _get_expected_tables():
            fks = self.inspector.get_foreign_keys(table_name)
            orm_table = Base.metadata.tables[table_name]
            # Build expected FK set from ORM metadata
            # ForeignKey.target_fullname gives "table.column" format
            expected_fks = set()
            for fk_constraint in orm_table.foreign_key_constraints:
                referred = fk_constraint.referred_table.name
                constrained = tuple(c.name for c in fk_constraint.columns)
                expected_fks.add((referred, constrained))
            actual_fks = {(fk["referred_table"], tuple(fk["constrained_columns"]))
                         for fk in fks}
            # Check each expected FK is present
            for exp_referred, exp_constrained in expected_fks:
                self.assertIn((exp_referred, exp_constrained), actual_fks,
                              f"FK missing on '{table_name}': {exp_constrained} -> {exp_referred}")


class TestMigrationDowngradeReupgrade(unittest.TestCase):
    """Test 3: Downgrade then re-upgrade produces a consistent schema."""

    def setUp(self):
        self.tmpdir = tempfile.mkdtemp()
        self.db_path = os.path.join(self.tmpdir, "test_roundtrip.db")
        self.db_url = f"sqlite:///{self.db_path}"
        self.engine = create_engine(self.db_url)

    def tearDown(self):
        self.engine.dispose()
        for f in os.listdir(self.tmpdir):
            os.remove(os.path.join(self.tmpdir, f))
        os.rmdir(self.tmpdir)

    def test_downgrade_removes_all_tables(self):
        """Downgrading to base should remove all application tables."""
        cfg = _get_alembic_cfg(self.db_url)
        command.upgrade(cfg, "head")
        command.downgrade(cfg, "base")

        # Re-create inspector (engine may cache old state)
        inspector = inspect(self.engine)
        tables = set(inspector.get_table_names()) - {"alembic_version"}
        self.assertEqual(tables, set(), f"Tables remain after downgrade: {tables}")

    def test_reupgrade_recreates_schema(self):
        """After downgrade, re-upgrade should recreate the full schema."""
        cfg = _get_alembic_cfg(self.db_url)

        # Full cycle: upgrade -> downgrade -> upgrade
        command.upgrade(cfg, "head")
        command.downgrade(cfg, "base")
        command.upgrade(cfg, "head")

        inspector = inspect(self.engine)
        actual_tables = set(inspector.get_table_names()) - {"alembic_version"}
        expected_tables = _get_expected_tables()

        self.assertEqual(actual_tables, expected_tables,
                         f"After round-trip, missing: {expected_tables - actual_tables}\n"
                         f"After round-trip, extra: {actual_tables - expected_tables}")

    def test_reupgrade_recreates_indexes(self):
        """After downgrade, re-upgrade should recreate all indexes."""
        cfg = _get_alembic_cfg(self.db_url)
        expected_indexes = _get_expected_indexes()

        command.upgrade(cfg, "head")
        command.downgrade(cfg, "base")
        command.upgrade(cfg, "head")

        inspector = inspect(self.engine)
        for idx_name, idx_info in expected_indexes.items():
            table_name = idx_info["table"]
            table_indexes = {i["name"]: i for i in inspector.get_indexes(table_name)}
            self.assertIn(idx_name, table_indexes,
                          f"After round-trip, index '{idx_name}' missing from '{table_name}'")

    def test_reupgrade_stamps_correct_version(self):
        """After round-trip, alembic_version should match current head."""
        cfg = _get_alembic_cfg(self.db_url)

        command.upgrade(cfg, "head")
        command.downgrade(cfg, "base")
        command.upgrade(cfg, "head")

        with self.engine.connect() as conn:
            result = conn.execute(text("SELECT version_num FROM alembic_version"))
            versions = [r[0] for r in result]

        self.assertEqual(len(versions), 1)
        self.assertEqual(versions[0], "0003_lineage")


class TestMigrationUrlOwnership(unittest.TestCase):
    """settings.DATABASE_URL is the single owner of the migration target.

    alembic.ini used to hardcode ``sqlalchemy.url = sqlite:///sentinelcert.db``,
    which silently beat any DATABASE_URL override (e.g. Docker's
    ``sqlite:////app/data/...`` volume): alembic reported success against the
    wrong file and the app database ended up with zero tables.
    """

    def setUp(self):
        self.tmpdir = tempfile.mkdtemp()
        self.fresh_db = os.path.join(self.tmpdir, "fresh_env.db")
        self.repo_db = os.path.join(os.getcwd(), "sentinelcert.db")
        self.repo_mtime_before = (
            os.path.getmtime(self.repo_db) if os.path.exists(self.repo_db) else None
        )

    def tearDown(self):
        for f in os.listdir(self.tmpdir):
            os.remove(os.path.join(self.tmpdir, f))
        os.rmdir(self.tmpdir)

    def test_alembic_ini_does_not_hardcode_sqlalchemy_url(self):
        """alembic.ini must not own the DB URL — env.py fills it from settings."""
        cfg = Config("alembic.ini")
        self.assertFalse(
            cfg.get_main_option("sqlalchemy.url"),
            "alembic.ini must not define sqlalchemy.url; env.py sets it from "
            "settings.DATABASE_URL so overrides are never ignored",
        )

    def test_upgrade_follows_database_url_env_override(self):
        """A DATABASE_URL override must receive the schema (the Docker failure mode)."""
        script = (
            "from alembic.config import Config\n"
            "from alembic import command\n"
            "command.upgrade(Config('alembic.ini'), 'head')\n"
        )
        env = dict(os.environ, DATABASE_URL=f"sqlite:///{self.fresh_db}")
        proc = subprocess.run(
            [sys.executable, "-c", script],
            env=env,
            capture_output=True,
            text=True,
        )
        self.assertEqual(proc.returncode, 0, msg=proc.stderr)

        self.assertTrue(os.path.exists(self.fresh_db), "override DB was never created")

        engine = create_engine(f"sqlite:///{self.fresh_db}")
        with engine.connect() as conn:
            version = conn.execute(
                text("SELECT version_num FROM alembic_version")
            ).scalar()
        self.assertEqual(version, "0003_lineage")
        tables = set(inspect(engine).get_table_names()) - {"alembic_version"}
        self.assertEqual(tables, _get_expected_tables())
        engine.dispose()

        # The override must not fall through to the default database.
        if self.repo_mtime_before is not None:
            self.assertEqual(os.path.getmtime(self.repo_db), self.repo_mtime_before)


if __name__ == "__main__":
    unittest.main()
