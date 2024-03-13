# SPDX-FileCopyrightText: 2023 Pôle d'Expertise de la Régulation Numérique <contact.peren@finances.gouv.fr>
#
# SPDX-License-Identifier: MIT
from functools import wraps

from nio import Event, InviteMemberEvent, MatrixRoom, ToDeviceEvent, UnknownEvent, MegolmEvent, RoomMessageText

from .config import logger, bolt_lib_config
from .client import MatrixClient


def properly_fail(function):
    """use this decorator so that your async callback never crash, log the error and return a message to the room"""

    @wraps(function)
    def decorated(room: MatrixRoom, message: Event, matrix_client: MatrixClient):
        function_instance = function(room, message, matrix_client)

        async def inner():
            try:
                return await function_instance
            except Exception as unexpected_exception:  # noqa
                await matrix_client.send_text_message(room.room_id, "failed to answer")
                logger.warning(f"command failed with exception : {unexpected_exception}")
            finally:
                await matrix_client.room_typing(room.room_id, typing_state=False)

        return inner()

    return decorated


class Callbacks:
    """A class for handling callbacks."""

    def __init__(self, matrix_client: MatrixClient):
        self.matrix_client = matrix_client
        self.startup = []
        self.client_callback = []

    def register_on_message_event(self, func, matrix_client) -> None:
        def wrapped_func(*args, **kwargs):
            return func(*args, matrix_client=matrix_client, **kwargs)

        self.client_callback.append((wrapped_func, RoomMessageText))

    def register_on_custom_event(self, func, event: Event):
        self.client_callback.append((func, event))

    def register_on_reaction_event(self, func):
        async def new_func(room, event):
            if event.type == "m.reaction":
                await func(room, event, event.source["content"]["m.relates_to"]["key"])

        self.client_callback.append((new_func, UnknownEvent))

    def register_on_startup(self, func):
        self.startup.append(func)

    async def setup_callbacks(self):
        """Add callbacks to async_client"""
        if bolt_lib_config.join_on_invite:
            self.matrix_client.add_event_callback(self.invite_callback, InviteMemberEvent)

        self.matrix_client.add_event_callback(self.decryption_failure, MegolmEvent)

        for function, event in self.client_callback:
            if issubclass(event, ToDeviceEvent):
                self.matrix_client.add_to_device_callback(function, event)
            else:
                self.matrix_client.add_event_callback(function, event)

    async def invite_callback(self, room: MatrixRoom, event: InviteMemberEvent):
        """Callback for handling invites."""
        if not event.membership == "invite":
            return

        try:
            await self.matrix_client.join(room.room_id)
            logger.info(f"Joined {room.room_id}")
        except Exception as join_room_exception:
            logger.info(f"Failed to join {room.room_id}", join_room_exceptions=join_room_exception)

    async def decryption_failure(self, room: MatrixRoom, event: MegolmEvent):
        """Callback for handling decryption errors."""
        if not isinstance(event, MegolmEvent):
            return

        logger.error(
            f"Failed to decrypt message: {event.event_id} from {event.sender} in {room.room_id}. "
            "If this error persists despite verification, reset the crypto session by deleting "
            f"{self.matrix_client.matrix_config.store_path} and {self.matrix_client.auth.session_stored_file_path}. "
            "You will have to verify any verified devices anew."
        )
        await self.matrix_client.send_text_message(
            room.room_id,
            "Failed to decrypt your message. Make sure encryption is enabled in my config and "
            "either enable sending messages to unverified devices or verify me if possible.",
            msgtype="m.notice",
        )
