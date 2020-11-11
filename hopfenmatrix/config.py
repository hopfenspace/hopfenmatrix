import logging
import json
import sys

logger = logging.getLogger(__name__)


class JsonConfig(dict):

    def __init__(self, config_path=None):
        self["matrix"] = {
            "user_id": "@bot:example.org",
            "user_password": "1234",
            "homeserver": "https://example.org",
            "device_id": "device0",
            "device_name": "Some Matrix Bot"
        }
        self["storage"] = {
            "database": "sqlite://bot.db",
            "store_path": "./store"
        }
        self["logging"] = {
            "level": "INFO",
            "format": "%(asctime)s | %(name)s [%(levelname)s] %(message)s",
            "file_logging": {
                "enabled": False,
                "filepath": "bot.log"
            },
            "console_logging": {
                "enabled": True
            }
        }

        # Hook for a subclass
        self.init()

        # Load config
        if config_path is not None:
            with open(config_path) as f:
                self.update(json.load(f))

        self.setup_logging()

    def setup_logging(self):
        formatter = logging.Formatter(self["logging"]["format"])

        logger.setLevel(self["logging"]["level"])

        if self["logging", "file_logging"]["enabled"]:
            handler = logging.FileHandler(
                self["logging"]["file_logging"]["filepath"]
            )
            handler.setFormatter(formatter)
            logger.addHandler(handler)

        if self["logging"]["console_logging"]["enabled"]:
            handler = logging.StreamHandler(sys.stdout)
            handler.setFormatter(formatter)
            logger.addHandler(handler)

    @property
    def store_path(self):
        return self["storage"]["store_path"]

    @property
    def database(self):
        db_path = self["storage"]["database"]
        sqlite_scheme = "sqlite://"
        postgres_scheme = "postgres://"
        if db_path.startswith(sqlite_scheme):
            return {
                "type": "sqlite",
                "connection_string": db_path[len(sqlite_scheme):],
            }
        elif db_path.startswith(postgres_scheme):
            return {
                "type": "postgres",
                "connection_string": db_path
            }
        else:
            raise ValueError("Invalid connection string in config 'storage.database'")

    def init(self):
        pass
