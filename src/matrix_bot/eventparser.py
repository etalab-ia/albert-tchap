# SPDX-FileCopyrightText: 2021 - 2022 Isaac Beverly <https://github.com/imbev>
# SPDX-FileCopyrightText: 2023 Pôle d'Expertise de la Régulation Numérique <contact.peren@finances.gouv.fr>
#
# SPDX-License-Identifier: MIT

from dataclasses import dataclass
from functools import wraps
from typing import Generic, TypeVar

from nio import Event, MatrixRoom, RoomMessageText

from .config import logger
from .room_utils import room_is_direct_message
from .client import MatrixClient


class EventNotConcerned(Exception):
    """Exception to say that the current event is not concerned by this parser"""


def ignore_when_not_concerned(function):
    """decorator to use with async function using EventParser"""

    @wraps(function)
    def decorated(*args, **kwargs):
        function_instance = function(*args, **kwargs)

        async def inner():
            try:
                return await function_instance
            except EventNotConcerned:
                return

        return inner()

    return decorated


E = TypeVar("E", bound=Event)


@dataclass
class EventParser(Generic[E]):
    """
    Parse the current event for the callbacks.
    Many useful methods that raises a EventNotConcerned when the action do not concern the current event
    """

    room: MatrixRoom
    event: E
    matrix_client: MatrixClient
    log_usage: bool = False

    def is_from_userid(self, userid: str) -> bool:
        return self.sender_id() == userid

    def is_from_this_bot(self) -> bool:
        return self.is_from_userid(self.matrix_client.user_id)

    def room_is_direct_message(self) -> bool:
        return room_is_direct_message(self.room)

    def sender_id(self):
        return self.event.sender

    def sender_username(self) -> str:
        return self.room.users[self.event.sender].name

    def do_not_accept_own_message(self) -> None:
        """
        :raise EventNotConcerned: if the message is written by the bot.
        """
        if self.is_from_this_bot():
            raise EventNotConcerned

    def only_on_direct_message(self) -> None:
        """
        :raise EventNotConcerned: if the room is a not a direct message room.
        """
        if not self.room_is_direct_message():
            raise EventNotConcerned

    def only_on_salons(self) -> None:
        """
        :raise EventNotConcerned: if the room is a direct message room.
        """
        if self.room_is_direct_message():
            raise EventNotConcerned


class MessageEventParser(EventParser):
    event: RoomMessageText

    def _command(self, body: str, command: str, prefix="!", command_name: str = "") -> str:
        command_prefix = f"{prefix}{command}"
        if not body.startswith(command_prefix):
            raise EventNotConcerned
        command_payload = body.removeprefix(command_prefix)
        if self.log_usage:
            logger.info("Handling command", command=command_name or command, command_payload=command_payload)
        return command_payload

    def command(self, command: str, prefix="!", command_name: str = "") -> str:
        """
        if the event is concerned by the command, returns the text after the command. Raise EventNotConcerned otherwise

        :param command: the command that is to be recognized.
        :param prefix: the prefix for this command (default is !).
        :param command_name: name of the command, for logging purposes.
        :return: the text after the command
        :raise EventNotConcerned: if the current event is not concerned by the command.
        """
        return self._command(body=self.event.body, command=command, prefix=prefix, command_name=command_name)

    async def hl(self, consider_hl_when_direct_message=True, command_prefix: str = ""):
        """
        if the event is a hl (highlight, i.e begins with the name of the bot),
        returns the text after the hl. Raise EventNotConcerned otherwise

        :param consider_hl_when_direct_message: if True, consider a direct message as an highlight.
        :param command_prefix: if given, will ignore messages beginning by this command in a direct message
        :return: the text after the highlight
        :raise EventNotConcerned: if the current event is not concerned by the command.
        """
        display_name = await self.matrix_client.get_display_name()
        if not display_name:
            display_name = ""
        if consider_hl_when_direct_message and self.room_is_direct_message():
            if self.event.body.startswith(command_prefix):
                raise EventNotConcerned
            return self._command(
                body=self.event.body.removeprefix(display_name).removeprefix(": "),
                command="",
                prefix="",
                command_name="mention",
            )
        return self.command(display_name, prefix="", command_name="mention").removeprefix(": ")
