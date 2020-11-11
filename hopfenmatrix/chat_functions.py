"""
Collection of helper functions for interacting with the chat
"""

import logging

from markdown import markdown
from nio import SendRetryError

logger = logging.getLogger(__name__)


async def send_text_to_room(client, room_id, message, notice=True, markdown_convert=True):
    """
    Send text to a matrix room

    :param client: the client to communicate to matrix with
    :type client: nio.AsyncClient
    :param room_id: the ID of the room to send the message to
    :type room_id: str
    :param message: the message content
    :type message: str
    :param notice: whether the message should be sent with an "m.notice" message type (will not ping users)
    :type notice: bool
    :param markdown_convert: whether to convert the message content to markdown.
    :type markdown_convert: bool
    """
    # Determine whether to ping room members or not
    msg_type = "m.notice" if notice else "m.text"

    content = {
        "msgtype": msg_type,
        "format": "org.matrix.custom.html",
        "body": message,
    }

    if markdown_convert:
        content["formatted_body"] = markdown(message)

    try:
        await client.room_send(
            room_id, "m.room.message", content, ignore_unverified_devices=True,
        )
    except SendRetryError:
        logger.exception(f"Unable to send message response to {room_id}")
