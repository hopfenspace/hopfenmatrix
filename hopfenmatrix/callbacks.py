import asyncio
import logging
from functools import wraps
from typing import Callable, List

from nio import MatrixRoom, Event, JoinError, AsyncClient

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


def debug() -> Callback:
    async def callback(room: MatrixRoom, event: Event) -> None:
        logger.debug(f"Received event: {repr(event)}")
    return callback


##########
# Filter #
##########

def filter_allowed_rooms(room_ids: List[str]) -> Filter:
    def filter_(room: MatrixRoom, event: Event) -> bool:
        return room.room_id in room_ids
    return filter_


def filter_allowed_users(user_ids: List[str]) -> Filter:
    def filter_(room: MatrixRoom, event: Event) -> bool:
        return event.sender in user_ids
    return filter_
