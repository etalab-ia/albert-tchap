# SPDX-FileCopyrightText: 2023 Pôle d'Expertise de la Régulation Numérique <contact.peren@finances.gouv.fr>
# SPDX-FileCopyrightText: 2024 Etalab <etalab@modernisation.gouv.fr>
#
# SPDX-License-Identifier: MIT

import time
import traceback
from collections import defaultdict
from dataclasses import dataclass

from matrix_bot.client import MatrixClient
from matrix_bot.config import logger
from matrix_bot.eventparser import EventNotConcerned, EventParser
from nio import Event, RoomMemberEvent, RoomMessageText

from bot_msg import AlbertMsg
from config import COMMAND_PREFIX, Config
from core_llm import (
    generate,
    generate_sources,
    get_available_models,
    get_available_modes,
)
from tchap_utils import get_cleanup_body, get_previous_messages, get_thread_messages, isa_reply_to


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
        help_message: str | None,
        hidden: bool,
        func,
    ):
        self.function_register[name] = {
            "name": name,
            "group": group,
            "onEvent": onEvent,
            "command": command,
            "prefix": prefix,
            "help": help_message,
            "hidden": hidden,
            "func": func,
        }

    def activate_and_retrieve_group(self, group_name: str) -> list:
        features = []
        for name, feature in self.function_register.items():
            if feature["group"] == group_name:
                self.activated_functions |= {name}
                features.append(feature)
        return features

    def is_valid_command(self, command) -> bool:
        return command in [
            feature["command"]
            for name, feature in self.function_register.items()
            if name in self.activated_functions
        ]

    def get_help(self, config: Config) -> str:
        cmds = self._get_cmds(config)
        model_url = f"https://huggingface.co/{config.albert_model}"
        model_short_name = config.albert_model.split("/")[-1]
        return AlbertMsg.help(model_url, model_short_name, cmds)

    def show_commands(self, config: Config) -> str:
        cmds = self._get_cmds(config)
        return AlbertMsg.commands(cmds)

    def _get_cmds(self, config: Config) -> list[str]:
        cmds = set(
            feature["help"]
            for name, feature in self.function_register.items()
            if name in self.activated_functions
            and feature["help"]
            and not feature["hidden"]
            and not (feature.get("command") == "sources" and config.albert_mode == "norag")
        )
        return sorted(list(cmds))


command_registry = CommandRegistry({}, set())
user_configs = defaultdict(lambda: Config())


def register_feature(
    group: str,
    onEvent: Event,
    command: str | None = None,
    prefix: str = COMMAND_PREFIX,
    help: str | None = None,
    hidden: bool = False,
):
    def decorator(func):
        command_registry.add_command(
            name=func.__name__,
            group=group,
            onEvent=onEvent,
            command=command,
            prefix=prefix,
            help_message=help,
            hidden=hidden,
            func=func,
        )
        return func

    return decorator


@register_feature(
    group="basic",
    onEvent=RoomMessageText,
    command="aide",
    help=AlbertMsg.shorts["help"],
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
    config.update_last_activity()
    time.sleep(3)  # wait for the room to be ready - otherwise the encryption seems to be not ready
    await matrix_client.room_typing(ep.room.room_id)
    await matrix_client.send_markdown_message(ep.room.room_id, command_registry.get_help(config))


@register_feature(
    group="albert",
    onEvent=RoomMessageText,
    command="reset",
    help=AlbertMsg.shorts["reset"],
)
async def albert_reset(ep: EventParser, matrix_client: MatrixClient):
    config = user_configs[ep.sender]
    if config.albert_with_history:
        config.update_last_activity()
        # Fast enough !
        #await matrix_client.room_typing(ep.room.room_id)
        config.albert_history_lookup = 0
        reset_message = AlbertMsg.reset
        reset_message += command_registry.show_commands(config)
        await matrix_client.send_markdown_message(
            ep.room.room_id, reset_message, msgtype="m.notice"
        )


@register_feature(
    group="albert",
    onEvent=RoomMessageText,
    command="conversation",
    help=AlbertMsg.shorts["conversation"],
    hidden=True,
)
async def albert_conversation(ep: EventParser, matrix_client: MatrixClient):
    config = user_configs[ep.sender]
    await matrix_client.room_typing(ep.room.room_id)
    if config.albert_with_history:
        config.albert_with_history = False
        config.albert_history_lookup = 0
        message = "Le mode conversation est désactivé."
    else:
        config.update_last_activity()
        config.albert_with_history = True
        message = "Le mode conversation est activé."
    await matrix_client.send_text_message(ep.room.room_id, message)


@register_feature(
    group="albert",
    onEvent=RoomMessageText,
    command="debug",
    help=AlbertMsg.shorts["debug"],
    hidden=True,
)
async def albert_debug(ep: EventParser, matrix_client: MatrixClient):
    config = user_configs[ep.sender]
    await matrix_client.room_typing(ep.room.room_id)
    debug_message = AlbertMsg.debug(config)
    await matrix_client.send_markdown_message(ep.room.room_id, debug_message)


@register_feature(
    group="albert",
    onEvent=RoomMessageText,
    command="model",
    help=AlbertMsg.shorts["reset"],
    hidden=True,
)
async def albert_model(ep: EventParser, matrix_client: MatrixClient):
    config = user_configs[ep.sender]
    await matrix_client.room_typing(ep.room.room_id)
    commands = ep.event.body.split()
    # Get all available models
    all_models = get_available_models(config)
    if len(commands) <= 1:
        message = (
            f"La commande !model nécessite de donner un modèle parmi : {', '.join(all_models)}"
        )
    else:
        model = commands[1]
        if model not in all_models:
            message = f"Modèle inconnu. Les modèles disponibles sont : {', '.join(all_models)}"
        else:
            previous_model = config.albert_model
            config.albert_model = model
            message = f"Le modèle a été modifié : {previous_model} -> {model}"
    await matrix_client.send_text_message(ep.room.room_id, message)


@register_feature(
    group="albert",
    onEvent=RoomMessageText,
    command="mode",
    help=AlbertMsg.shorts["mode"],
    hidden=True,
)
async def albert_mode(ep: EventParser, matrix_client: MatrixClient):
    config = user_configs[ep.sender]
    await matrix_client.room_typing(ep.room.room_id)
    commands = ep.event.body.split()
    # Get all available mode for the current model
    all_modes = get_available_modes(config)
    all_modes += ["norag"]
    if len(commands) <= 1:
        message = f"La commande !mode nécessite de donner un mode parmi : {', '.join(all_modes)}"
    else:
        mode = commands[1]
        if mode not in all_modes:
            message = f"Mode inconnu. Les modes disponibles sont : {', '.join(all_modes)}"
        else:
            old_mode = config.albert_mode
            config.albert_mode = mode
            message = f"Le mode a été modifié : {old_mode} -> {mode}"
    await matrix_client.send_text_message(ep.room.room_id, message)


@register_feature(
    group="albert",
    onEvent=RoomMessageText,
    command="sources",
    help=AlbertMsg.shorts["sources"],
)
async def albert_sources(ep: EventParser, matrix_client: MatrixClient):
    config = user_configs[ep.sender]
    await matrix_client.room_typing(ep.room.room_id)

    try:
        if config.albert_stream_id:
            sources = generate_sources(config=config, stream_id=config.albert_stream_id)
            sources_msg = ""
            for source in sources:
                extra_context = ""
                if source.get("context"):
                    extra_context = f'({source["context"]})'
                sources_msg += f'- {source["title"]} {extra_context}: {source["url"]} \n'
        else:
            sources_msg = "Aucune source trouvée, veuillez me poser une question d'abord."
    except Exception:
        traceback.print_exc()
        await matrix_client.send_markdown_message(ep.room.room_id, AlbertMsg.failed, msgtype="m.notice")
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
    config = user_configs[ep.sender]
    ep.only_on_direct_message()

    initial_history_lookup = config.albert_history_lookup

    user_query = ep.event.body
    if user_query.startswith(COMMAND_PREFIX):
        raise EventNotConcerned

    if config.albert_with_history and config.is_conversation_obsolete:
        config.albert_history_lookup = 0
        obsolescence_in_minutes = str(config.conversation_obsolescence // 60)
        reset_message = AlbertMsg.reset_notif(obsolescence_in_minutes)
        await matrix_client.room_typing(ep.room.room_id)
        await matrix_client.send_markdown_message(
            ep.room.room_id, reset_message, msgtype="m.notice"
        )

    config.update_last_activity()
    await matrix_client.room_typing(ep.room.room_id, typing_state=True, timeout=180_000)
    try:
        # Build the messages  history
        # --
        is_reply_to = isa_reply_to(ep.event)
        if is_reply_to:
            # Use the targeted thread history
            # --
            message_events = await get_thread_messages(
                config, ep, max_rewind=config.albert_max_rewind
            )
        else:
            # Use normal history
            # --
            # Add the current user query in the history count
            config.albert_history_lookup += 1
            message_events = await get_previous_messages(
                config,
                ep,
                history_lookup=config.albert_history_lookup,
                max_rewind=config.albert_max_rewind,
            )

        # Map event to list of message {role, content} and cleanup message body
        # @TODO: If bot should answer in multi-user canal, we could catch is own name here.
        messages = [
            {"role": "user", "content": get_cleanup_body(event)}
            if event.source["sender"] == ep.sender
            else {"role": "assistant", "content": get_cleanup_body(event)}
            for event in message_events
        ]

        # Empty chunk (i.e at startup)
        if not messages:
            messages = [{"role": "user", "content": user_query}]

        answer = generate(config=config, messages=messages)

    except Exception as albert_err:
        logger.error(f"{albert_err}")
        traceback.print_exc()
        # Send an error message to the user
        await matrix_client.send_markdown_message(ep.room.room_id, AlbertMsg.failed, msgtype="m.notice")
        # Redirect the error message to the errors room if it exists
        if config.errors_room_id:
            await matrix_client.send_markdown_message(
                config.errors_room_id, AlbertMsg.error_debug(albert_err, config)
            )

        config.albert_history_lookup = initial_history_lookup
        return

    logger.debug(f"{user_query=}")
    logger.debug(f"{answer=}")

    reply_to = None
    if is_reply_to:
        # "content" ->  "m.mentions": {"user_ids": [ep.sender]},
        # "content" -> "m.relates_to": {"m.in_reply_to": {"event_id": ep.event.event_id}},
        reply_to = ep.event.event_id

    try:  # sometimes the async code fail (when input is big) with random asyncio errors
        await matrix_client.send_markdown_message(ep.room.room_id, answer, reply_to=reply_to)
    except Exception as llm_exception:  # it seems to work when we retry
        logger.error(f"asyncio error when sending message {llm_exception=}. retrying")
        time.sleep(1)
        await matrix_client.send_markdown_message(ep.room.room_id, answer, reply_to=reply_to)

        config.albert_history_lookup = initial_history_lookup
        return

    # Add agent answer in the history count
    if not is_reply_to:
        config.albert_history_lookup += 1


@register_feature(
    group="albert",
    onEvent=RoomMessageText,
    help=None,
)
async def albert_wrong_command(ep: EventParser, matrix_client: MatrixClient):
    config = user_configs[ep.sender]
    user_query = ep.event.body
    command = user_query.split()[0][1:]
    if not user_query.startswith(COMMAND_PREFIX) or command_registry.is_valid_command(command):
        raise EventNotConcerned

    cmds_msg = command_registry.show_commands(config)
    await matrix_client.send_markdown_message(ep.room.room_id, AlbertMsg.unknown_command(cmds_msg), msgtype="m.notice")
