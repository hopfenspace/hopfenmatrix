import logging
from time import sleep
import asyncio

from aiohttp import ClientConnectionError, ServerDisconnectedError
from nio import (
    AsyncClient,
    LocalProtocolError,
    LoginError,
)

from hopfenmatrix.config import Config

logger = logging.getLogger(__name__)


async def run(client: AsyncClient, config: Config, callbacks: list = []):
    """
    This function runs a client as user in an endless loop.

    :param client: the client object to use
    :type client: AsyncClient
    :param config: the config to run with
    :type config: Config
    :param callbacks: Async callback functions
    :type callbacks: list
    """

    # Keep trying to reconnect on failure (with some time in-between)
    while True:
        try:
            # Try to login with the configured username/password
            try:
                logger.info(f"Trying to log in as {config.matrix.user_id}")
                login_response = await client.login(
                    password=config.matrix.user_password, device_name=config.matrix.device_name,
                )

                # Check if login failed
                if type(login_response) == LoginError:
                    logger.error("Failed to login: %s", login_response.message)
                    return False

            except LocalProtocolError as e:
                # There's an edge case here where the user hasn't installed the correct C
                # dependencies. In that case, a LocalProtocolError is raised on login.
                logger.fatal(
                    "Failed to login. Have you installed the correct dependencies? "
                    "https://github.com/poljar/matrix-nio#installation "
                    "Error: %s",
                    e,
                )
                return False

            # Login succeeded!
            logger.info(f"Logged in as {config.matrix.user_id}")

            # Sync client first time
            await asyncio.get_event_loop().create_task(client.sync(full_state=True, timeout=30000))

            # Call all callbacks
            for callback in callbacks:
                asyncio.get_event_loop().create_task(callback)

            await client.sync_forever(timeout=30000, full_state=True, loop_sleep_time=100)

        except (ClientConnectionError, ServerDisconnectedError):
            logger.warning("Unable to connect to homeserver, retrying in 15s...")

            # Sleep so we don't bombard the server with login requests
            sleep(15)
        except KeyboardInterrupt:
            logger.info("Exiting bot")
        finally:
            # Make sure to close the client connection on disconnect
            await client.close()
