import logging
from time import sleep

from aiohttp import ClientConnectionError, ServerDisconnectedError
from nio import (
    AsyncClient,
    LocalProtocolError,
    LoginError,
)

logger = logging.getLogger(__name__)


async def run(client: AsyncClient, user: str, password: str, device: str):
    """
    This function runs a client as user in an endless loop.

    :param client: the client object to use
    :type client: AsyncClient
    :param user: the user to run as
    :type user: str
    :param password: the user password to authenticate
    :type password: str
    :param device: the device to run as
    :type device: str
    """

    # Keep trying to reconnect on failure (with some time in-between)
    while True:
        try:
            # Try to login with the configured username/password
            try:
                login_response = await client.login(
                    password=password, device_name=device,
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

            logger.info(f"Logged in as {user}")
            await client.sync_forever(timeout=30000, full_state=True)

        except (ClientConnectionError, ServerDisconnectedError):
            logger.warning("Unable to connect to homeserver, retrying in 15s...")

            # Sleep so we don't bombard the server with login requests
            sleep(15)
        finally:
            # Make sure to close the client connection on disconnect
            await client.close()
