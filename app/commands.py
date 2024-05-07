# SPDX-FileCopyrightText: 2023 Pôle d'Expertise de la Régulation Numérique <contact.peren@finances.gouv.fr>
# SPDX-FileCopyrightText: 2024 Etalab <etalab@modernisation.gouv.fr>
#
# SPDX-License-Identifier: MIT

from collections import defaultdict
from dataclasses import dataclass

from config import ALLOWED_DOMAINS, COMMAND_PREFIX, Config
from matrix_bot.client import MatrixClient
from matrix_bot.config import logger
from matrix_bot.eventparser import EventParser
from nio import Event, RoomMemberEvent, RoomMessageText
from pyalbert_utils import generate, generate_sources, new_chat


@dataclass
class CommandRegistry:
    function_register: dict
    activated_functions: set[str]

    def add_command(
        self,
        name: str,
        group: str,
        onEvent: Event,
        command: str | None,
        prefix: str | None,
        help: str | None,
        func,
    ):
        self.function_register[name] = {
            "name": name,
            "group": group,
            "onEvent": onEvent,
            "command": command,
            "prefix": prefix,
            "help": help,
            "func": func,
        }

    def activate_and_retrieve_group(self, group_name: str):
        features = []
        for name, feature in self.function_register.items():
            if feature["group"] == group_name:
                self.activated_functions |= {name}
                features.append(feature)
        return features

    def is_valid_command(self, command):
        return command in [
            feature["command"]
            for name, feature in self.function_register.items()
            if name in self.activated_functions
        ]

    def get_help(self, config: Config) -> str:
        cmds = [
            feature["help"]
            for name, feature in self.function_register.items()
            if name in self.activated_functions and feature["help"]
        ]

        help_message = "Bonjour, je m'appelle Albert et je suis votre assistant automatique dédié aux questions légales et administratives. N'hésitez pas à me soumettre vos interrogations, je suis là pour vous aider au mieux.\n\n"
        help_message += "Attention :\n\n"
        help_message += "- Je suis en phase de pré-test, il est possible que je sois en maintenance et que je ne réponde pas ou de manière imprécise\n"
        help_message += "- Les échanges que j'ai avec vous peuvent être déchiffrés et stockés pour analyser mes performances ultérieurement\n"
        help_message += "\n"
        help_message += "Vous pouvez utiliser les commandes spéciales suivantes :\n\n"
        help_message += "- " + "\n- ".join(cmds)
        help_message += "\n\n"
        if config.with_history:
            help_message += "Le mode conversation est activé."
        else:
            help_message += "Le mode conversation est désactivé."

        return help_message

    def show_commands(self):
        cmds = [
            feature["help"]
            for name, feature in self.function_register.items()
            if name in self.activated_functions and feature["help"]
        ]

        available_cmd = "Les commandes spéciales suivantes sont disponibles :\n\n"
        available_cmd += "- " + "\n- ".join(cmds)
        return available_cmd


command_registry = CommandRegistry({}, set())
user_configs = defaultdict(lambda: Config())


def register_feature(
    group: str,
    onEvent: Event,
    command: str | None = None,
    prefix: str = COMMAND_PREFIX,
    help: str | None = None,
):
    def decorator(func):
        command_registry.add_command(
            name=func.__name__,
            group=group,
            onEvent=onEvent,
            command=command,
            prefix=prefix,
            help=help,
            func=func,
        )
        return func

    return decorator


@register_feature(
    group="basic",
    onEvent=RoomMessageText,
    command="aide",
    help=f"**{COMMAND_PREFIX}aide** : afficher l'aide",
)
async def help(ep: EventParser, matrix_client: MatrixClient):
    config = user_configs[ep.sender]
    await matrix_client.room_typing(ep.room.room_id)
    await matrix_client.send_markdown_message(ep.room.room_id, command_registry.get_help(config))


@register_feature(
    group="albert",
    onEvent=RoomMemberEvent,
    # @DEBUG: RoomCreateEvent is not captured ?
    help=None,
)
async def albert_welcome(ep: EventParser, matrix_client: MatrixClient):
    """
    Receive the join/invite event and send the welcome/help message
    """
    config = user_configs[ep.sender]
    ep.only_on_direct_message()
    ep.only_on_join()
    await matrix_client.send_markdown_message(ep.room.room_id, command_registry.get_help(config))


@register_feature(
    group="albert",
    onEvent=RoomMessageText,
    command="reset",
    help=f"**{COMMAND_PREFIX}reset** : remettre à zéro la conversation avec Albert",
)
async def albert_reset(ep: EventParser, matrix_client: MatrixClient):
    config = user_configs[ep.sender]
    ep.only_allowed_sender()
    await matrix_client.room_typing(ep.room.room_id)
    if config.with_history:
        config.chat_id = new_chat(config)
        reset_message = "La conversation a été remise à zéro."
        await matrix_client.send_text_message(ep.room.room_id, reset_message)


@register_feature(
    group="albert_debug",
    onEvent=RoomMessageText,
    command="conversation",
    help=f"**{COMMAND_PREFIX}conversation** : activer/désactiver le mode conversation",
)
async def albert_conversation(ep: EventParser, matrix_client: MatrixClient):
    config = user_configs[ep.sender]
    ep.only_allowed_sender()
    await matrix_client.room_typing(ep.room.room_id)
    if config.with_history:
        config.with_history = False
        reset_message = "Le mode conversation est activé."
    else:
        config.with_history = True
        reset_message = "Le mode conversation est désactivé."
    await matrix_client.send_text_message(ep.room.room_id, reset_message)


@register_feature(
    group="albert",
    onEvent=RoomMessageText,
    command="sources",
    help=f"**{COMMAND_PREFIX}sources** : afficher les références utilisées lors de la dernière réponse",
)
async def albert_sources(ep: EventParser, matrix_client: MatrixClient):
    config = user_configs[ep.sender]
    ep.only_allowed_sender()
    await matrix_client.room_typing(ep.room.room_id)

    try:
        if config.stream_id:
            sources = generate_sources(config=config, stream_id=config.stream_id)
            sources_msg = ""
            for source in sources:
                extra_context = ""
                if source.get("context"):
                    extra_context = f'({source["context"]})'
                sources_msg += f'- {source["title"]} {extra_context}: {source["url"]} \n'
        else:
            sources_msg = "Aucune source trouvée, veuillez me poser une question d'abord."
    except Exception as albert_exception:
        await matrix_client.send_markdown_message(
            ep.room.room_id, f"\u26a0\ufe0f **Serveur erreur**\n\n{albert_exception}"
        )
        return

    await matrix_client.send_text_message(ep.room.room_id, sources_msg)


@register_feature(
    group="albert",
    onEvent=RoomMessageText,
    help=None,
)
async def albert_answer(ep: EventParser, matrix_client: MatrixClient):
    """
    Receive a message event which is not a command, send the prompt to Albert API and return the response to the user
    """
    # user_prompt: str = await ep.hl()
    config = user_configs[ep.sender]
    ep.only_allowed_sender()
    user_prompt = ep.event.body
    if user_prompt[0] != COMMAND_PREFIX:
        ep.only_on_direct_message()
        query = user_prompt
        await matrix_client.room_typing(ep.room.room_id, typing_state=True, timeout=180_000)
        try:
            answer = generate(config=config, query=query)
        except Exception as albert_exception:
            await matrix_client.send_markdown_message(
                ep.room.room_id, f"\u26a0\ufe0f **Serveur erreur**\n\n{albert_exception}"
            )
            return

        logger.debug(f"{query=}")
        logger.debug(f"{answer=}")
        try:  # sometimes the async code fail (when input is big) with random asyncio errors
            await matrix_client.send_markdown_message(ep.room.room_id, answer)
        except Exception as llm_exception:  # it seems to work when we retry
            logger.error(f"asyncio error when sending message {llm_exception=}. retrying")
            await matrix_client.send_markdown_message(ep.room.room_id, answer)
    else:
        command = user_prompt.split()[0][1:]
        if not command_registry.is_valid_command(command):
            await matrix_client.send_markdown_message(
                ep.room.room_id,
                f"\u26a0\ufe0f **Commande inconnue**\n\n{command_registry.show_commands()}",
            )
            return
