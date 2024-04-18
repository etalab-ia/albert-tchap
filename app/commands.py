# SPDX-FileCopyrightText: 2023 Pôle d'Expertise de la Régulation Numérique <contact.peren@finances.gouv.fr>
# SPDX-FileCopyrightText: 2024 Etalab/Datalab <etalab@modernisation.gouv.fr>
#
# SPDX-License-Identifier: MIT

from dataclasses import dataclass

from nio import Event, MatrixRoom

from config import COMMAND_PREFIX, env_config
from matrix_bot.callbacks import properly_fail
from matrix_bot.client import MatrixClient
from matrix_bot.config import logger
from matrix_bot.eventparser import MessageEventParser, ignore_when_not_concerned
from pyalbert_utils import generate


@dataclass
class CommandRegistry:
    function_register: dict
    activated_functions: set[str]

    def add_command(self, *, name: str, help: str | None, group: str, func):
        self.function_register[name] = {"help": help, "group": group, "func": func}

    def get_help(self) -> str:
        cmds = [
            function["help"]
            for name, function in self.function_register.items()
            if name in self.activated_functions and function["help"]
        ]

        help_message = "Bonjour, je suis Albert, l'assistant administratif de l'administration française. Je suis à l'écoute de toutes vos questions que vous pouvez poser ici.\n\n"
        help_message += "Veuillez noter que :\n\n"
        help_message += "- Je suis en phase de pré-test, il est possible que je sois en maintenance et que je ne réponde pas ou de manière imprécise !\n"
        help_message += "- Les échanges que j'ai avec vous peuvent être déchiffrés et stockés pour analyser mes performances ultérieurement.\n"
        help_message += "\n"
        help_message += "Vous pouvez également utiliser les commandes spéciales suivantes :\n\n"
        help_message += "- " + "\n- ".join(cmds)
        return help_message

    def activate_and_retrieve_group(self, group_name: str):
        self.activated_functions |= {
            name
            for name, function in self.function_register.items()
            if function["group"] == group_name
        }
        return [
            function["func"]
            for name, function in self.function_register.items()
            if function["group"] == group_name
        ]


command_registry = CommandRegistry({}, set())


def register_feature(help: str | None, group: str):
    def decorator(func):
        command_registry.add_command(name=func.__name__, help=help, group=group, func=func)
        return func

    return decorator


@register_feature(help=f"**{COMMAND_PREFIX}aide** : donne l'aide", group="basic")
@properly_fail
@ignore_when_not_concerned
async def help(room: MatrixRoom, message: Event, matrix_client: MatrixClient):
    event_parser = MessageEventParser(room=room, event=message, matrix_client=matrix_client)
    event_parser.do_not_accept_own_message()
    event_parser.command("aide", prefix=COMMAND_PREFIX)
    logger.info("Handling command", command="help")
    await matrix_client.room_typing(room.room_id)
    await matrix_client.send_markdown_message(room.room_id, command_registry.get_help())


@register_feature(
    help=f"**{COMMAND_PREFIX}reset** : remet à zero la conversation avec Albert", group="albert"
)
@properly_fail
@ignore_when_not_concerned
async def albert_reset(room: MatrixRoom, message: Event, matrix_client: MatrixClient):
    event_parser = MessageEventParser(room=room, event=message, matrix_client=matrix_client)
    event_parser.do_not_accept_own_message()
    event_parser.command("reset", prefix=COMMAND_PREFIX)
    await matrix_client.room_typing(room.room_id)
    # TODO: Albert reset stream
    reset: str = "La conversation a été remise à zéro."
    logger.info("Handling command", command="reset")
    await matrix_client.send_text_message(room.room_id, reset)


@register_feature(help=None, group="albert")
@properly_fail
@ignore_when_not_concerned
async def albert_answer(room: MatrixRoom, message: Event, matrix_client: MatrixClient):
    """
    Send the prompt to Albert and return the response
    """
    event_parser = MessageEventParser(
        room=room, event=message, matrix_client=matrix_client, log_usage=True
    )
    event_parser.do_not_accept_own_message()
    # user_prompt: str = await event_parser.hl()
    user_prompt: str = event_parser.event.body
    if user_prompt[0] != COMMAND_PREFIX:
        query = user_prompt
        await matrix_client.room_typing(room.room_id, typing_state=True, timeout=180_000)
        try:
            answer = generate(config=env_config, query=query)
        except Exception as albert_exception:
            await matrix_client.send_markdown_message(
                room.room_id, f"\u26a0\ufe0f **Serveur erreur**\n\n{albert_exception}"
            )
            return

        # await matrix_client.send_text_message(
        #    room.room_id, f"Pour remettre à zéro la conversation, tapez `{COMMAND_PREFIX}reset`"
        # )  # TODO

        logger.info(f"{query=}")
        logger.info(f"{answer=}")
        try:  # sometimes the async code fail (when input is big) with random asyncio errors
            await matrix_client.send_markdown_message(room.room_id, answer)
        except Exception as llm_exception:  # it seems to work when we retry
            logger.error(f"asyncio error when sending message {llm_exception=}. retrying")
            await matrix_client.send_markdown_message(room.room_id, answer)
