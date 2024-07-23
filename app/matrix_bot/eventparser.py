# SPDX-FileCopyrightText: 2021 - 2022 Isaac Beverly <https://github.com/imbev>
# SPDX-FileCopyrightText: 2023 Pôle d'Expertise de la Régulation Numérique <contact.peren@finances.gouv.fr>
# SPDX-FileCopyrightText: 2024 Etalab <etalab@modernisation.gouv.fr>
#
# SPDX-License-Identifier: MIT
from dataclasses import dataclass

from nio import Event, MatrixRoom, RoomMessageText

from .client import MatrixClient
from .config import logger
from .room_utils import room_is_direct_message


class EventNotConcerned(Exception):
    """Exception to say that the current event is not concerned by this parser"""


@dataclass
class EventParser:
    """
    Parse the current event for the callbacks.
    Many useful methods that raises a EventNotConcerned when the action do not concern the current event
    """

    room: MatrixRoom
    event: Event
    matrix_client: MatrixClient
    log_usage: bool = False

    @property
    def sender(self) -> str:
        return self.event.sender

    def is_from_userid(self, userid: str) -> bool:
        return self.sender_id() == userid

    def is_from_this_bot(self) -> bool:
        return self.is_from_userid(self.matrix_client.user_id)

    def room_is_direct_message(self) -> bool:
        return room_is_direct_message(self.room)

    def sender_id(self) -> str:
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

    def only_on_join(self) -> None:
        """
        :raise EventNotConcerned: if the event is not a join event (the bot has been invited)
        """
        if not self.event.source.get("content", {}).get("membership") == "invite":
            raise EventNotConcerned

    def is_command(self):
        return False


class MessageEventParser(EventParser):
    event: RoomMessageText
    command: list[str] | None = None

    def parse_command(self, commands: str | list[str], prefix: str, command_name: str = ""):
        """
        if the event is concerned by the command, returns the command line as a list.
        Raise EventNotConcerned otherwise.

        :param command: the command that is to be recognized.
        :param prefix: the prefix for this command (default is !).
        :param command_name: name(s) of the command, for logging purposes.
        :return: the text after the command
        :raise EventNotConcerned: if the current event is not concerned by the command.
        """
        commands = [commands] if isinstance(commands, str) else commands
        body = self.event.body.strip()
        user_command = body.split()
        command = [commands[0]] + user_command[1:]

        if not any([f"{prefix}{c}" == user_command[0] for c in commands]):
            raise EventNotConcerned

        if self.log_usage:
            logger.info(
                "Handling command", command=command_name or command[0], command_payload=command[1:]
            )

        self.command = command

    def is_command(self, prefix: str) -> bool:
        return self.event.body.strip().startswith(prefix)

    def get_command(self) -> list[str] | None:
        return self.command

    # @deprecated: Not used/tested
    async def hl(self, consider_hl_when_direct_message=True) -> str:
        """
        if the event is a hl (highlight, i.e begins with the name of the bot),
        returns the text after the hl. Raise EventNotConcerned otherwise

        :param consider_hl_when_direct_message: if True, consider a direct message as an highlight.
        :return: the text after the highlight
        :raise EventNotConcerned: if the current event is not concerned by the command.
        """
        display_name = await self.matrix_client.get_display_name()
        if consider_hl_when_direct_message and self.room_is_direct_message():
            return self.get_command_line(
                "",
                prefix="",
                body=self.event.body.removeprefix(display_name).removeprefix(": "),
                command_name="mention",
            )
        return self.get_command_line(display_name, prefix="", command_name="mention").removeprefix(
            ": "
        )
