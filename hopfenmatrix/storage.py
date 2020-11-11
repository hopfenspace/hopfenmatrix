import logging

logger = logging.getLogger(__name__)


class Storage(object):
    """
    Base for a db-based storage.

    To use it, subclass it and overwrite `_initial_setup`, `_run_migrations` and `LATEST_MIGRATION_VERSION`.
    """

    LATEST_MIGRATION_VERSION = 0

    def __init__(self, db_type: str, connection_string: str):
        """
        Setup the database

        Runs an initial setup or migrations depending on whether a database file has already
        been created

        :param db_type: one of "sqlite" or "postgres"
        :type db_type: str
        :param connection_string: a connection string that can be fed to each respective db library's `connect` method
        :type connection_string: str
        """

        # Open the db connection
        if self.db_type == "sqlite":
            import sqlite3

            # Initialize a connection to the database, with autocommit on
            self.conn = sqlite3.connect(connection_string, isolation_level=None)

        elif self.db_type == "postgres":
            import psycopg2

            self.conn = psycopg2.connect(connection_string)

            # Autocommit on
            self.conn.set_isolation_level(0)

        self.db_type = db_type
        self.cursor = self.conn.cursor()

        # Try to check the current migration version
        migration_level = 0
        try:
            self._execute("SELECT version FROM migration_version")
            row = self.cursor.fetchone()
            migration_level = row[0]

        # When it failed, the db has to be setup first
        except Exception:
            logger.info("Performing initial database setup...")

            # Set up the migration_version table
            self._execute(
                """
                CREATE TABLE migration_version (
                    version INTEGER PRIMARY KEY
                )
                """
            )

            # Initially set the migration version to 0
            self._execute(
                """
                INSERT INTO migration_version (
                    version
                ) VALUES (?)
                """,
                (0,),
            )

            # Set up any other necessary database
            self._initial_setup()

            logger.info("Database setup complete")

        # Run migrations if necessary
        finally:
            if migration_level < self.LATEST_MIGRATION_VERSION:
                logger.info("Performing database migrations "
                            f"from version {migration_level} to {self.LATEST_MIGRATION_VERSION}...")
                self._run_migrations(migration_level)
                logger.info("Database migrations complete")

        logger.info(f"Database initialization of type '{self.db_type}' complete")

    def _execute(self, *args):
        """
        A wrapper around cursor.execute that transforms placeholder ?'s to %s for postgres
        """
        if self.db_type == "postgres":
            self.cursor.execute(args[0].replace("?", "%s"), *args[1:])
        else:
            self.cursor.execute(*args)

    def _initial_setup(self):
        """
        Initial setup of the database
        """
        pass

    def _run_migrations(self, current_migration_version: int):
        """
        Execute database migrations. Migrates the database to the `latest_migration_version`

        :param current_migration_version: the migration version that the database is currently at
        :type current_migration_version: int
        """
        pass
