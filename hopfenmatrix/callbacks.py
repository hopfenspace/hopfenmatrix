import asyncio
import logging
import re
import html
from functools import wraps
from typing import Callable, List, Union

from nio import MatrixRoom, Event, JoinError, RoomMessageText

logger = logging.getLogger(__name__)

Callback = Callable[[MatrixRoom, Event], None]
Filter = Callable[[MatrixRoom, Event], bool]


class CommandCallback:
    """
    This class represents a command callback.

    :param command_callback: This represents Callable
    :type command_callback: Callable
    :param accepted_aliases: Aliases the command accepts
    :type accepted_aliases: list[str], str
    :param alias_is_regex: Specify True, if the aliases are regexes
    :type alias_is_regex: bool
    :param make_default: Make this command default, if prefix was found and no other alias matches. Defaults to false
    :type make_default: bool
    :param command_syntax: The syntax of the command, without the alias
    :type command_syntax: str
    :param description: Description of the command.
    :type description: str
    """
    def __init__(
            self,
            command_callback: Callable,
            accepted_aliases: Union[List[str], str],
            *,
            alias_is_regex: bool = False,
            make_default: bool = False,
            command_syntax: str = "",
            description: str = ""
    ):
        self.command_callback = command_callback
        self.accepted_aliases = accepted_aliases[0] \
            if isinstance(accepted_aliases, list) and len(accepted_aliases) == 1 else accepted_aliases
        self.alias_is_regex = alias_is_regex
        self.make_default = make_default
        self.command_syntax = command_syntax
        self.description = description


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

async def _send_help(api, room, event):
    message = f"{api.config.matrix.bot_description}\n\n"
    formatted_message = f"{api.config.matrix.bot_description}<br><br>"
    for command in api.command_callbacks:
        aliases = command.accepted_aliases
        syntax = command.command_syntax
        description = command.description
        message += f"\t- {aliases if isinstance(aliases, str) else ', '.join(aliases)}" \
                   f"{(' ' + syntax) if syntax else ''}: {description}\n"
        formatted_message += f"&emsp;- <code>{aliases if isinstance(aliases, str) else '<' + ', '.join(aliases) + '>'}" \
                             f"{(' ' + html.escape(syntax)) if syntax else ''}</code>: {description}<br>"
    await api.send_message(message, room.room_id, formatted_message=formatted_message)


def auto_join(
        api,
        retries: int = 3
) -> Callback:
    """
    Create a callback which joins the room the event came from.

    :param api: Api object
    :type api: MatrixBot
    :param retries: the number of times to retry, if the joining fails
    :type retries: int
    :return: a callback
    """
    async def callback(room: MatrixRoom, event: Event) -> None:
        if event.membership == "join":
            logger.info(f"Got invite to {room.room_id} from {event.sender}.")

            # Attempt to join 3 times before giving up
            for attempt in range(1, retries + 1):
                await asyncio.sleep(1)
                result = await api.client.join(room.room_id)
                if isinstance(result, JoinError):
                    logger.error(
                        f"Error joining room {room.room_id} (attempt {attempt}/{retries}): {result.message}"
                    )
                else:
                    break
            else:
                logger.error(f"Unable to join room: {room.room_id}")
        elif event.membership == "invite":
            if api.enable_initial_info:
                logger.info(f"Joined room {room.room_id}, enable_initial_info is configured, sending initial info")
                await api.client.sync(full_state=True)
                await _send_help(api, room, event)

    return callback


def help_command_callback():
    """
    This message is a callback command for generating a default help command
    """
    async def callback(api, room, event):
        if event.sender == api.client.user:
            return
        await _send_help(api, room, event)

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
        logger.debug(f"Received {msg} from {event.sender} in room {room.room_id}")
        pattern = re.compile(r"^" + api.config.matrix.command_prefix + r"( |$)")
        has_command_prefix = pattern.match(msg)

        # Check if command_prefix is sent or if we are in a direct chat
        if not has_command_prefix and len(room.users) > 2:
            logger.debug(f"Room is not private, but no command prefix was used")
            return

        # Remove command prefix, leading and trailing whitespaces
        msg = msg.lstrip(api.config.matrix.command_prefix).strip()
        event.stripped_body = msg
        if event.body != event.stripped_body:
            logger.debug(f"Stripped command_prefix: {msg}")

        # method for finding commands
        async def find_command(message: str) -> bool:
            if command.alias_is_regex:
                alias_pattern = re.compile(message)
                if alias_pattern.findall(msg):
                    logger.info(f"Found command in msg: {msg}")
                    await command_callback(api, room, event)
                    return True
            else:
                if msg.startswith(message):
                    logger.info(f"Found command in msg: {msg}")
                    await command_callback(api, room, event)
                    return True
            return False

        # Iterate over all registered command callbacks
        found = False
        for command in api.command_callbacks:
            command_callback = command.command_callback
            aliases = command.accepted_aliases
            if isinstance(aliases, list):
                for alias in aliases:
                    found = await find_command(alias)
                    if found:
                        break
            else:
                found = await find_command(aliases)
                if found:
                    break

        default_command = [x for x in api.command_callbacks if x.make_default]
        if not found and len(default_command) > 0:
            logger.info(f"Found no command in msg, executing default command")
            await default_command[0].command_callback(api, room, event)

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
