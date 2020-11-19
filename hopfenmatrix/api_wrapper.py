import enum
import logging
import os
from collections import Coroutine

import typing
from nio import AsyncClient, SendRetryError, AsyncClientConfig, InviteMemberEvent, RoomMessage

from hopfenmatrix.callbacks import apply_filter, auto_join, filter_allowed_rooms, filter_allowed_users
from hopfenmatrix.config import Config
from hopfenmatrix.run import run

logger = logging.getLogger(__name__)


class MessageType(enum.Enum):
    """
    This class is used to map message types in python.
    For further information see: https://matrix.org/docs/guides/client-server-api#sending-messages
    """
    TEXT = "m.text"
    NOTICE = "m.notice"
    IMAGE = "m.image"
    AUDIO = "m.audio"
    VIDEO = "m.video"
    LOCATION = "m.location"
    EMOTE = "m.emote"


class EventType(enum.Enum):
    """
    This class is used to map the available event types.
    """
    ROOM_INVITE = InviteMemberEvent
    "This event represents the event of being invited to a room"
    ROOM_MESSAGE = RoomMessage
    "This is the event when receiving a message"


class ApiWrapper:
    """
    This class is used to wrap common functions of the API.

    :param display_name: Set the display name of the bot.
    :type display_name: str
    :param config: This config is used instead of generating or loading one. If not specified, the default configuration
    is used
    :type config: Config
    :param config_path: Path to the configuration file. If not existent, the default configuration will be created.
    Defaults to config.json
    :type config_path: str
    :param config_class: Config class. Will be loaded or generated from config_path
    :type config_class: typing.Type[Config]
    """
    def __init__(
            self, *,
            display_name: str = None,
            config: Config = None,
            config_path: str = "config.json",
            config_class: typing.Type[Config] = None
    ):
        if config:
            self.config = config
        elif config_class:
            self.config = config.from_json(config_path)
        else:
            self.config = Config().from_json(config_path)
        self.client = self._new_async_client()
        self.display_name = display_name
        self.coroutine_callbacks = []

    def _new_async_client(
            self,
            client_config: AsyncClientConfig = None,
            ssl: bool = None,
            proxy: str = None
    ) -> AsyncClient:
        """
        Use the config values to create an AsyncClient

        :param client_config: a nio config object for AsyncClient's constructor
        :type client_config: AsyncClientConfig
        :param ssl: flag whether to use ssl
        :type ssl: bool
        :param proxy: address for a proxy
        :type proxy: str
        """
        if not client_config:
            client_config = AsyncClientConfig(
                max_limit_exceeded=0,
                max_timeouts=0,
                store_sync_tokens=True,
                encryption_enabled=True,
            )
        if not os.path.isdir(self.config.matrix.database_directory):
            os.mkdir(self.config.matrix.database_directory)
        return AsyncClient(
            self.config.matrix.homeserver,
            self.config.matrix.user_id,
            device_id=self.config.matrix.device_id,
            store_path=self.config.matrix.database_directory,
            config=client_config,
            ssl=ssl,
            proxy=proxy
        )

    async def start_bot(self):
        await run(self)

    def set_auto_join(
            self,
            *,
            allowed_rooms: list = None,
            allowed_users: list = None
    ) -> None:
        """
        This method is used to set the auto join callback methods.

        :param allowed_users: List of users which the bot will accept invites from. Format: @user_name:homeserver.org
        :type allowed_users: list
        :param allowed_rooms: List of rooms which the bot will accept invites for. Format: !random_id:homeserver.org
        :type allowed_rooms: list
        """
        if not allowed_rooms and not allowed_users:
            self.client.add_event_callback(auto_join(self.client), EventType.ROOM_INVITE.value)
        else:
            if allowed_rooms:
                self.client.add_event_callback(
                    apply_filter(auto_join(self.client), filter_allowed_rooms(allowed_rooms))
                )
            if allowed_users:
                self.client.add_event_callback(
                    apply_filter(auto_join(self.client), filter_allowed_users(allowed_users))
                )

    def add_coroutine_callback(self, coroutine: Coroutine) -> None:
        """
        This method is used to add a coroutine to the loop. Must be called before start_bot gets executed. The
        coroutine is added after the bot has logged in.

        :param coroutine: The Coroutine which will be added to the loop. Must have client, config as parameter
        :type coroutine: Coroutine
        """
        self.coroutine_callbacks.append(coroutine)

    async def send_message(
            self,
            message,
            room_id,
            *,
            formatted_message=None,
            send_as_notice=False
    ) -> None:
        """
        This message is used to wrap the client.room_send function of matrix-nio.

        :param message: The unformatted message to send
        :type message: str
        :param room_id: The room_id to send the message to, can also be a list of room_ids
        :type room_id: Union[str, list]
        :param formatted_message: The formatted message to send. If not specified the unformatted message is sent instead.
        :type formatted_message: str
        :param send_as_notice: Set to True to send messages silently.
        :type send_as_notice: bool
        """
        content = {
            "msgtype": MessageType.NOTICE.value if send_as_notice else MessageType.TEXT.value,
            "format": "org.matrix.custom.html",
            "body": message,
            "formatted_message": formatted_message if formatted_message else message
        }
        if isinstance(room_id, list):
            for room in room_id:
                await self._send(content, room)
        else:
            await self._send(content, room_id)

    async def send_reply(
            self,
            message,
            room_id,
            event_id_to_reply,
            *,
            send_as_notice=False
    ) -> None:
        """
        This method is used to allow the user to make a rich reply to another message.
        For further information see: https://matrix.org/docs/spec/client_server/r0.6.1#rich-replies

        :param message: Message to send in reply to another message
        :type message: str
        :param room_id: ID of the room in which the reply should be sent in.
        :type room_id: str
        :param event_id_to_reply: The event id to reply to
        :type event_id_to_reply: str
        :param send_as_notice: Set True if message should be sent silently. Defaults to False.
        :type send_as_notice: bool
        """
        formatted_message = """<mx-reply>
            <blockquote>
                <a href="https://matrix.to/#/!:./:.">In reply to</a>
            </blockquote>
        </mx-reply>
        """
        content = {
            "msgtype": MessageType.NOTICE.value if send_as_notice else MessageType.TEXT.value,
            "format": "org.matrix.custom.html",
            "body": message,
            "formatted_message": formatted_message,
            "m.relates_to": {
                "m.in_reply_to": {
                    "event_id": event_id_to_reply
                }
            }
        }
        await self._send(content, room_id)

    async def _send(
            self,
            content: dict,
            room_id: str,
            *,
            ignore_unverified_devices=True
    ) -> None:
        """
        This message is used as a helper function for sending messages.

        :param content: See https://matrix.org/docs/spec/client_server/r0.6.1#m-text
        :type content: dict
        :param room_id: ID of the room to send the message to.
        :type room_id: str
        :param ignore_unverified_devices: Ignore unverified devices. Defaults to True
        :type ignore_unverified_devices: bool
        """
        try:
            await self.client.room_send(
                room_id,
                "m.room.message",
                content,
                ignore_unverified_devices=ignore_unverified_devices
            )
        except SendRetryError:
            logger.exception(f"Unable to send message to room {room_id}.")
