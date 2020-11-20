import asyncio
import logging
from functools import wraps
from typing import Callable, List, Union

from nio import MatrixRoom, Event, JoinError, AsyncClient, RoomMessageText

logger = logging.getLogger(__name__)


Callback = Callable[[MatrixRoom, Event], None]
Filter = Callable[[MatrixRoom, Event], bool]


def apply_filter(callback: Callback,
                 filter_: Filter
                 ) -> Callback:
    """
    Take a callback and apply a filter to it.

    A filter is a function which takes a room and an event, and returns True if this event should be processed.

    :param callback: callback function
    :type callback: Callable[[MatrixRoom, Event], None]
    :param filter_: filter function
    :type filter_: Callable[[MatrixRoom, Event], bool]
    :return: filtered callback function
    :rtype: Callable[[MatrixRoom, Event], None]
    """
    @wraps(callback)
    async def new_callback(room: MatrixRoom, event: Event) -> None:
        if filter_(room, event):
            await callback(room, event)
    return new_callback


############
# Callback #
############
def auto_join(client: AsyncClient,
              retries: int = 3
              ) -> Callback:
    """
    Create a callback which joins the room the event came from.

    :param client: the client to join with
    :type client: AsyncClient
    :param retries: the number of times to retry, if the joining fails
    :type retries: int
    :return: a callback
    """
    async def callback(room: MatrixRoom, event: Event) -> None:
        logger.info(f"Got invite to {room.room_id} from {event.sender}.")

        # Attempt to join 3 times before giving up
        for attempt in range(1, retries+1):
            await asyncio.sleep(1)
            result = await client.join(room.room_id)
            if isinstance(result, JoinError):
                logger.error(
                    f"Error joining room {room.room_id} (attempt {attempt}/{retries}): {result.message}"
                )
            else:
                break
        else:
            logger.error(f"Unable to join room: {room.room_id}")
    return callback


def command_handler(api) -> Callback:
    """
    This handler checks for commands in a received message and forwards them to their respective callback.

    :param api: The ApiWrapper object
    :type api: ApiWrapper
    """
    async def callback(room: MatrixRoom, event: RoomMessageText) -> None:
        msg = event.body

        # Check if the bot is the sender
        if event.sender == api.client.user:
            return

        logger.debug(f"Received a message from {event.sender} in room {room.room_id}")

        # Check if command_prefix is sent or if we are in a direct chat
        if not msg.startswith(api.config.matrix.command_prefix) and len(room.users) > 2:
            return

        # Remove command prefix, leading and trailing whitespaces
        msg = msg.lstrip(api.config.matrix.command_prefix).strip()

        # Iterate over all registered command callbacks
        for command in api.command_callbacks:
            command_callback = command[0]
            aliases = command[1]
            if isinstance(aliases, list):
                for alias in aliases:
                    if msg.startswith(alias):
                        await command_callback(api, room, event)
                        break
            else:
                if msg.startswith(aliases):
                    await command_callback(api, room, event)
                    break
        await asyncio.sleep(0.1)

    return callback


def debug() -> Callback:
    async def callback(room: MatrixRoom, event: Event) -> None:
        logger.debug(f"Received event: {repr(event)}")
    return callback


##########
# Filter #
##########

def filter_allowed_rooms(room_ids: Union[List[str], None]) -> Filter:
    def filter_(room: MatrixRoom, event: Event) -> bool:
        return room.room_id in room_ids if room_ids else True
    return filter_


def filter_allowed_users(user_ids: Union[List[str], None]) -> Filter:
    def filter_(room: MatrixRoom, event: Event) -> bool:
        return event.sender in user_ids if user_ids else True
    return filter_
