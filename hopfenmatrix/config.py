import logging
import sys
from typing import Dict, Any

from nio import AsyncClient, AsyncClientConfig

logger = logging.getLogger()


class ConfigError(RuntimeError):
    """An error while loading the config"""
    pass


class Namespace(dict):
    """
    A namespace is a python dict whose values can be accessed like attributes.

    It also ensures that its keys are identifier strings.
    The point is solely to have nicer syntax.
    """

    def __getattr__(self, key):
        return self.__getitem__(key)

    def __setattr__(self, key, value):
        self.__setitem__(key, value)

    def __setitem__(self, key, value):
        if isinstance(key, str) and key.isidentifier():
            super().__setitem__(key, value)
        else:
            raise KeyError("Key must be identifier strings")


class Config(Namespace):
    """
    A namespace (dict) containing an applications config.

    The constructor takes no arguments and initialises all possible config options with some default values.

    How to use:
    - Use the classmethod `from_json` to load a json-formatted config file.
    - To add your own options just subclass this class and extends or overwrite the constructor.
    - Use `Namespace` objects to create sections.
    """

    def __init__(self):
        super().__init__()
        self.matrix = Namespace()
        self.matrix.user_id = "@bot:example.org"
        self.matrix.user_password = "1234"
        self.matrix.homeserver = "https://example.org"
        self.matrix.device_id = "device0"
        self.matrix.device_name = "Some Matrix Bot"
        self.matrix.database_directory = "./store"

        self.logging = Namespace()
        self.logging.level = "INFO"
        self.logging.format = "%(asctime)s | %(name)s [%(levelname)s] %(message)s"

        self.logging.file_logging = Namespace()
        self.logging.file_logging.enabled = False
        self.logging.file_logging.filepath = "bot.log"

        self.logging.console_logging = Namespace()
        self.logging.console_logging.enabled = True

    @classmethod
    def from_dict(cls, dct: Dict[str, Any]) -> "Config":
        """
        Create a config instance and load the values from a dict.

        :param dct: the config values
        :type dct: Dict[str, Any]
        :return: config instance
        :rtype: Config
        """
        config = cls()
        cls._update(config, dct)
        return config

    @classmethod
    def from_json(cls, config_file: str) -> "Config":
        """
        Load a json file and create a config instance from it.

        :param config_file: path to json file to load
        :type config_file: str
        :return: config instance
        :rtype: Config
        """
        import json

        with open(config_file) as f:
            dct = json.load(f)
        return cls.from_dict(dct)

    @staticmethod
    def _update(dct, dct2):
        for key, value in dct2.items():
            if key not in dct:
                raise ConfigError(f"Unexpected config option: '{key}'")
            elif isinstance(value, dict):
                Config._update(dct[key], value)
            else:
                dct[key] = value

    def setup_logging(self):
        """
        Use the config values to setup the logging module.
        """
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

    def new_async_client(self, client_config: AsyncClientConfig, ssl: bool = None, proxy: str = None) -> AsyncClient:
        """
        Use the config values to create an AsyncClient

        :param client_config: an nio config object for AsyncClient's constructor
        :type client_config: AsyncClientConfig
        :param ssl: flag whether to use ssl
        :type ssl: bool
        :param proxy: address for a proxy
        :type proxy: str
        :return: an AsyncClient instance
        :rtype: AsyncClient
        """
        return AsyncClient(
            self.matrix.homeserver,
            self.matrix.user_id,
            device_id=self.matrix.device_id,
            store_path=self.matrix.store_path,
            config=client_config,
            ssl=ssl,
            proxy=proxy
        )
