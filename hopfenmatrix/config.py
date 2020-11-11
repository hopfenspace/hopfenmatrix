import logging
import json
import sys

logger = logging.getLogger()


class JsonConfig(dict):

    def __init__(self, config_path=None):
        super().__init__()
        self["matrix"] = {
            "user_id": "@bot:example.org",
            "user_password": "1234",
            "homeserver": "https://example.org",
            "device_id": "device0",
            "device_name": "Some Matrix Bot",
            "database_directory": "./store"
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

        if self["logging"]["file_logging"]["enabled"]:
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
    def homeserver(self):
        return self["matrix"]["homeserver"]

    @property
    def user_id(self):
        return self["matrix"]["user_id"]

    @property
    def user_password(self):
        return self["matrix"]["user_password"]

    @property
    def device_id(self):
        return self["matrix"]["device_id"]

    @property
    def device_name(self):
        return self["matrix"]["device_name"]

    @property
    def store_path(self):
        return self["matrix"]["database_directory"]

    def init(self):
        pass
