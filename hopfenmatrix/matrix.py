import enum
import logging
import os
import typing

import mutagen
import aiofiles.os
from PIL import Image
from nio import (AsyncClient, SendRetryError, AsyncClientConfig, InviteMemberEvent, RoomMessage, RoomMessageText,
                 MatrixRoom, UploadResponse, LocalProtocolError)
import magic

from hopfenmatrix.callbacks import apply_filter, auto_join, filter_allowed_rooms, filter_allowed_users, command_handler, \
    help_command_callback, CommandCallback
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
    ROOM_MESSAGE_TEXT = RoomMessageText
    "This is the event when a text message is received"


class MatrixBot:
    """
    This class is used to wrap common functions of the API.

    :param display_name: Set the display name of the bot.
    :type display_name: str
    :param enable_initial_info: Specify True if the bot should send an info message when entering a room.
    :type enable_initial_info: bool
    :param config: This config is used instead of generating or loading one. If not specified, the default configuration
    is used
    :type config: Config
    :param config_path: Path to the configuration file. If not existent, the default configuration will be created.
    Defaults to config_old.json
    :type config_path: str
    :param config_class: Config class. Will be loaded or generated from config_path
    :type config_class: typing.Type[Config]
    """

    def __init__(
            self, *,
            display_name: str = None,
            enable_initial_info: bool = False,
            config: Config = None,
            config_path: str = "config.json",
            config_class: typing.Type[Config] = None
    ):
        if config:
            self.config = config
        elif config_class:
            self.config = config_class.from_json(config_path)
        else:
            self.config = Config().from_json(config_path)
        self.client = self._new_async_client()
        if display_name:
            self.config.matrix.display_name = display_name
        self.enable_initial_info = enable_initial_info
        self.coroutine_callbacks = []
        self.command_callbacks = []

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
                max_timeouts=2,
                store_sync_tokens=True,
                encryption_enabled=True,
            )
        if not os.path.isdir(self.config.matrix.database_directory):
            os.mkdir(self.config.matrix.database_directory)

        client = AsyncClient(
            self.config.matrix.homeserver,
            self.config.matrix.user_id,
            device_id=self.config.matrix.device_id,
            store_path=self.config.matrix.database_directory,
            config=client_config,
            ssl=ssl,
            proxy=proxy
        )

        if self.config.matrix.access_token:
            client.access_token = self.config.matrix.access_token
            client.user_id = self.config.matrix.user_id

        return client

    async def start_bot(self):
        """
        Use this method for starting the bot.
        """
        if self.command_callbacks:
            aliases = []
            for x in [x.accepted_aliases for x in self.command_callbacks]:
                if isinstance(x, list):
                    for y in x:
                        aliases.append(y)
                else:
                    aliases.append(x)
            if "help" not in aliases:
                self.register_command(
                    help_command_callback(),
                    accepted_aliases="help",
                    description="Prints the help page"
                )
        self.client.add_event_callback(command_handler(self), EventType.ROOM_MESSAGE_TEXT.value)
        await run(self)

    def set_auto_join(
            self,
            *,
            allowed_rooms: list = None,
            allowed_users: list = None,
    ) -> None:
        """
        This method is used to set the auto join callback methods.

        :param allowed_users: List of users which the bot will accept invites from. Format: @user_name:homeserver.org
        :type allowed_users: list
        :param allowed_rooms: List of rooms which the bot will accept invites for. Format: !random_id:homeserver.org
        :type allowed_rooms: list
        """
        if not allowed_rooms and not allowed_users:
            self.client.add_event_callback(auto_join(self), EventType.ROOM_INVITE.value)
        else:
            if allowed_rooms:
                self.client.add_event_callback(
                    apply_filter(auto_join(self), filter_allowed_rooms(allowed_rooms)),
                    EventType.ROOM_INVITE.value
                )
            else:
                self.client.add_event_callback(
                    apply_filter(auto_join(self), filter_allowed_rooms(None)),
                    EventType.ROOM_INVITE.value
                )
            if allowed_users:
                self.client.add_event_callback(
                    apply_filter(auto_join(self), filter_allowed_users(allowed_users)),
                    EventType.ROOM_INVITE.value
                )
            else:
                self.client.add_event_callback(
                    apply_filter(auto_join(self), filter_allowed_users(None)),
                    EventType.ROOM_INVITE.value
                )

    def register_command(
            self,
            command_callback: typing.Callable,
            accepted_aliases: typing.Union[list, str],
            *,
            alias_is_regex: bool = False,
            description: str = "",
            command_syntax: str = "",
            make_default: bool = False
    ) -> None:
        """
        This method is used to register a command.

        :param command_callback: Callback to the command handler
        :type command_callback: Callable
        :param accepted_aliases: Aliases which will be accepted.
        :type accepted_aliases: Union[list, str]
        :param alias_is_regex: Specify true, if the aliases are should be regexes
        :type alias_is_regex: bool
        :param description: A short description of the command, used in automatically generated help command
        :type description: str
        :param command_syntax: The syntax of the command, without the alias
        :type command_syntax: str
        :param make_default: If specified, the registered command will behave as "default" command. So when calling the
        bot with no or wrong parameters, this command is executed. Defaults to False
        :type make_default: bool
        """
        cmd = CommandCallback(
            command_callback,
            accepted_aliases,
            alias_is_regex=alias_is_regex,
            make_default=make_default,
            command_syntax=command_syntax,
            description=description
        )
        self.command_callbacks.append(cmd)

    def add_coroutine_callback(self, coroutine) -> None:
        """
        This method is used to add a coroutine to the loop. Must be called before start_bot gets executed. The
        coroutine is added after the bot has logged in.

        :param coroutine: The Coroutine which will be added to the loop. Must have client, config as parameter
        :type coroutine: Coroutine
        """
        self.coroutine_callbacks.append(coroutine)

    ################
    # Client calls #
    ################

    async def is_room_private(self, room: MatrixRoom) -> bool:
        """
        This method is used to check if the given room is a private chat. As there are no such things as private chats,
        private rooms are considered as such, if there are only 2 members, the bot and the other user.

        :param room: Room object, received by the bot
        :type room: MatrixRoom
        :returns: True, if room is considered as private, else False
        :rtype: bool
        """
        return len(room.users) <= 2

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
        :param room_id: The room to send the message to
        :type room_id: str
        :param formatted_message: The formatted message to send. If not specified the unformatted message is sent instead.
        :type formatted_message: str
        :param send_as_notice: Set to True to send messages silently.
        :type send_as_notice: bool
        """
        content = {
            "msgtype": MessageType.NOTICE.value if send_as_notice else MessageType.TEXT.value,
            "format": "org.matrix.custom.html",
            "body": message,
            "formatted_body": formatted_message if formatted_message else message
        }
        await self._send(content, room_id)

    async def send_reply(
            self,
            message,
            room_id,
            event,
            *,
            formatted_message=None,
            send_as_notice=False
    ) -> None:
        """
        This method is used to allow the user to make a rich reply to another message.
        For further information see: https://matrix.org/docs/spec/client_server/r0.6.11#rich-replies

        :param message: Message to send in reply to another message
        :type message: str
        :param room_id: Room in which the reply should be sent in.
        :type room_id: str
        :param event: The event to reply to
        :type event: RoomMessageText
        :param formatted_message: Formatted message to send.
        :type formatted_message: str
        :param send_as_notice: Set True if message should be sent silently. Defaults to False.
        :type send_as_notice: bool
        """
        fallback_body_first = event.body.split('\n')[0]
        fallback_body = ""
        if len(event.body.split('\n')) > 1:
            fallback_body = '\n> '.join(event.body.split('\n'))
        unformatted_message = f'> <{event.sender}> {fallback_body_first}\n{fallback_body}\n{message}'
        formatted_body = f"<mx-reply><blockquote><a href=\"https://matrix.to/#/{room_id}/{event.event_id}?via={room_id.split(':')[1]}\">In reply to</a> <a href=\"https://matrix.to/#/{event.sender}\">{event.sender}</a><br><br/>{event.body}</blockquote></mx-reply>{message if not formatted_message else formatted_message}"
        content = {
            "msgtype": MessageType.NOTICE.value if send_as_notice else MessageType.TEXT.value,
            "body": unformatted_message,
            "format": "org.matrix.custom.html",
            "formatted_body": formatted_body,
            "m.relates_to": {
                "m.in_reply_to": {
                    "event_id": event.event_id
                }
            }
        }
        await self._send(content, room_id)

    async def send_image(
            self,
            image_path: str,
            room: MatrixRoom,
            *,
            description=None
    ):
        """
        Send an image to a room.

        :param image_path: Path to image
        :type image_path: str
        :param room: Room to send the image to.
        :type room: MatrixRoom
        :param description: Description of the image. If not sets defaults to filename.
        :type description: str
        """
        if not description:
            description = os.path.basename(image_path)
        mime_type = magic.from_file(image_path, mime=True)
        img = Image.open(image_path)
        (width, height) = img.size
        file_stat = await aiofiles.os.stat(image_path)
        async with aiofiles.open(image_path, "r+b") as fh:
            resp, maybe_keys = await self.client.upload(fh,
                                                        content_type=mime_type,
                                                        filename=os.path.basename(image_path),
                                                        filesize=file_stat.st_size)
        if isinstance(resp, UploadResponse):
            logger.debug("Image was uploaded successfully to server. ")
        else:
            logger.warning(f"Failed to upload image. Failure response: {resp}")

        content = {
            "body": description,
            "info": {
                "size": file_stat.st_size,
                "mimetype": mime_type,
                "thumbnail_info": None,
                "w": width,
                "h": height,
                "thumbnail_url": None,
            },
            "msgtype": "m.image",
            "url": resp.content_uri,
        }
        await self._send(content, room.room_id)

    async def send_video(
            self,
            video_path: str,
            room: MatrixRoom,
            *,
            description=None
    ):
        """
        Send video to room.

        :param video_path: Path to video file.
        :type video_path: str
        :param room: Room to send the video to.
        :type room: MatrixRoom
        :param description: Description of the video. If not sets defaults to filename.
        :type description: str
        """
        if not description:
            description = os.path.basename(video_path)
        mime_type = magic.from_file(video_path, mime=True)
        file_stat = await aiofiles.os.stat(video_path)
        async with aiofiles.open(video_path, "r+b") as fh:
            resp, maybe_keys = await self.client.upload(fh,
                                                        content_type=mime_type,
                                                        filename=os.path.basename(video_path),
                                                        filesize=file_stat.st_size)
        content = {
            "body": description,
            "msgtype": "m.video",
            "url": resp.content_uri
        }
        await self._send(content, room.room_id, )

    async def send_file(
            self,
            file_path: str,
            room: MatrixRoom,
            *,
            description=None
    ):
        """
        This method is used to send a file to a room.

        :param file_path: Path to file.
        :type file_path: str
        :param room: Room to send the file to.
        :type room: MatrixRoom
        :param description: Description of the file.
        :type description: str
        """
        if not description:
            description = os.path.basename(file_path)
        mime_type = magic.from_file(file_path, mime=True)
        file_stat = await aiofiles.os.stat(file_path)
        async with aiofiles.open(file_path, "r+b") as fh:
            resp, maybe_keys = await self.client.upload(fh,
                                                        content_type=mime_type,
                                                        filename=os.path.basename(file_path),
                                                        filesize=file_stat.st_size)
        content = {
            "body": description,
            "filename": os.path.basename(file_path),
            "msgtype": "m.file",
            "url": resp.content_uri
        }
        await self._send(content, room.room_id)

    async def send_audio(
            self,
            audio_path,
            room,
            *,
            description=None
    ):
        """
        This method is used to send an audio file to a room.

        :param audio_path: Path to audio file.
        :type audio_path: str
        :param room: Room to send the audio file to.
        :type room: MatrixRoom
        :param description: Description of the file.
        :type description: str
        """
        if not description:
            description = os.path.basename(audio_path)
        mime_type = magic.from_file(audio_path, mime=True)
        file_stat = await aiofiles.os.stat(audio_path)
        audio = mutagen.File(audio_path)
        duration = audio.info.length
        async with aiofiles.open(audio_path, "r+b") as fh:
            resp, maybe_keys = await self.client.upload(fh,
                                                        content_type=mime_type,
                                                        filename=os.path.basename(audio_path),
                                                        filesize=file_stat.st_size)
        content = {
            "body": description,
            "info": {
                "duration": int(duration),
                "mimetype": mime_type,
                "size": file_stat.st_size
            },
            "msgtype": "m.audio",
            "url": resp.content_uri
        }
        await self._send(content, room.room_id)

    async def send_emote(
            self,
            emote: str,
            room: MatrixRoom,
            *,
            formatted_message: str = None
    ):
        """
        This method is used to send an emote to a room.

        :param emote: The emote to display.
        :type emote: str
        :param room: The room to send the emote to.
        :type room: MatrixRoom
        :param formatted_message: The HTML formatted emote.
        :type formatted_message: str
        """
        if not formatted_message:
            formatted_message = emote
        content = {
            "body": emote,
            "format": "org.matrix.custom.html",
            "formatted_body": formatted_message,
            "msgtype": "m.emote"
        }
        await self._send(content, room.room_id)

    async def send_location(
            self,
            location_description: str,
            location_uri: str,
            room: MatrixRoom
    ):
        """
        This method is used to send a location to a room.

        :param location_description: Description of the location
        :type location_description: str
        :param location_uri: Geo uri
        :type location_uri: str
        :param room: Room to send the location to.
        :type room: MatrixRoom
        """
        content = {
            "body": location_description,
            "format": "org.matrix.custom.html",
            "geo_uri": location_uri,
            "msgtype": "m.location"
        }
        await self._send(content, room.room_id)

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
        except (SendRetryError, LocalProtocolError):
            logger.error(f"Unable to send message to room {room_id}.")
