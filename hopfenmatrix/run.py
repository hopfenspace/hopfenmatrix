import logging
from time import sleep
import asyncio

from aiohttp import ClientConnectionError, ServerDisconnectedError
from nio import (
    LocalProtocolError,
    LoginError,
    SyncError,
)

logger = logging.getLogger(__name__)


async def run(
        api
):
    """
    This function runs a client as user in an endless loop.

    :param api: ApiWrapper which holds the config and the client
    :type api: ApiWrapper
    """

    if api.coroutine_callbacks is None:
        callbacks = []
    else:
        callbacks = api.coroutine_callbacks
    # Keep trying to reconnect on failure (with some time in-between)
    while True:
        try:
            if not api.client.access_token:
                # Try to login with the configured username/password
                try:
                    logger.info(f"Trying to log in as {api.config.matrix.user_id}")

                    login_response = await api.client.login(
                        password=api.config.matrix.user_password, device_name=api.config.matrix.device_name,
                    )

                    # Check if login failed
                    if type(login_response) == LoginError:
                        logger.error("Failed to login: %s", login_response.message)
                        return False

                    # Writing new config_file
                    if api.config.config_path:
                        api.config.matrix.access_token = api.client.access_token
                        api.config.to_json(api.config, api.config.config_path)
                        logger.debug(f"Received access_token, write to new config file to {api.config.config_path}")

                    # Login succeeded!
                    logger.info(f"Logged in as {api.config.matrix.user_id}")

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
            else:
                logger.warning("As the access_token isn't working right now, logging in with password")
                api.client.access_token = ""
                continue
                logger.info(f"Trying to log in as {api.config.matrix.user_id} with stored credentials")
                api.client.load_store()
                resp = await api.client.sync(full_state=True, timeout=5000)
                if isinstance(resp, SyncError):
                    api.client.access_token = ""
                    logger.error(f"Failed to login with stored credentials, trying to relogin with password")
                    continue
                logger.info(f"Logged in as {api.config.matrix.user_id}")

            # Sync client first time
            await asyncio.get_event_loop().create_task(api.client.sync(full_state=True, timeout=30000))

            # Set display name
            if api.config.matrix.display_name:
                await api.client.set_displayname(api.config.matrix.display_name)

            # Call all callbacks
            for callback in callbacks:
                asyncio.get_event_loop().create_task(callback)

            await api.client.sync_forever(timeout=30000, full_state=True, loop_sleep_time=100)

        except (ClientConnectionError, ServerDisconnectedError):
            logger.warning("Unable to connect to homeserver, retrying in 15s...")

            # Sleep so we don't bombard the server with login requests
            sleep(15)
        except KeyboardInterrupt:
            logger.info("Exiting bot")
        finally:
            # Make sure to close the client connection on disconnect
            await api.client.close()
