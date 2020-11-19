import enum
import logging

from nio import AsyncClient, SendRetryError

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


class ApiWrapper:
    """
    This class is used to wrap common functions of the API.

    :param client: The AsyncClient, has to be synced once in order to be able to send to rooms
    :type client: AsyncClient
    :param config: This config class to retrieve information about the bot
    :type config: Config
    """
    def __init__(self, client, config):
        self.client = client
        self.config = config

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
