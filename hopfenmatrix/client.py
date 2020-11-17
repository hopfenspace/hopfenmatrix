from nio import AsyncClientConfig, AsyncClient
from hopfenmatrix.config import Config


def new_async_client(
        config: Config,
        client_config: AsyncClientConfig,
        ssl: bool = None,
        proxy: str = None
) -> AsyncClient:
    """
    Use the config values to create an AsyncClient

    :param config: a hopfenmatrix config object
    :type config: Config
    :param client_config: a nio config object for AsyncClient's constructor
    :type client_config: AsyncClientConfig
    :param ssl: flag whether to use ssl
    :type ssl: bool
    :param proxy: address for a proxy
    :type proxy: str
    :return: an AsyncClient instance
    :rtype: AsyncClient
    """
    return AsyncClient(
        config.matrix.homeserver,
        config.matrix.user_id,
        device_id=config.matrix.device_id,
        store_path=config.matrix.database_directory,
        config=client_config,
        ssl=ssl,
        proxy=proxy
    )