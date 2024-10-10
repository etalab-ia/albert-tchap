# SPDX-FileCopyrightText: 2023 Pôle d'Expertise de la Régulation Numérique <contact.peren@finances.gouv.fr>
# SPDX-FileCopyrightText: 2024 Etalab <etalab@modernisation.gouv.fr>
#
# SPDX-License-Identifier: MIT

import asyncio
import traceback
from collections import defaultdict
from dataclasses import dataclass
from functools import wraps
import mimetypes

from matrix_bot.client import MatrixClient
from matrix_bot.config import logger
from matrix_bot.eventparser import EventNotConcerned, EventParser
from nio import Event, RoomMemberEvent, RoomMessageFile, RoomMessageText

from bot_msg import AlbertMsg
from config import COMMAND_PREFIX, Config
from core_llm import (
    generate,
    get_available_models,
    get_available_modes,
)
from iam import TchapIam
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
        aliases: list[str] | None,
        prefix: str | None,
        help_message: str | None,
        for_geek: bool,
        func,
    ):
        commands = [command] if command else None
        if aliases:
            commands += aliases

        self.function_register[name] = {
            "name": name,
            "group": group,
            "onEvent": onEvent,
            "commands": commands,
            "prefix": prefix,
            "help": help_message,
            "for_geek": for_geek,
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
        valid_commands = []
        for name, feature in self.function_register.items():
            if name in self.activated_functions:
                if feature.get("commands"):
                    valid_commands += feature["commands"]
        return command in valid_commands

    def get_help(self, config: Config, verbose: bool = False) -> str:
        cmds = self._get_cmds(config, verbose)
        model_url = f"https://huggingface.co/{config.albert_model}"
        model_short_name = config.albert_model.split("/")[-1]
        return AlbertMsg.help(model_url, model_short_name, cmds)

    def show_commands(self, config: Config) -> str:
        cmds = self._get_cmds(config)
        return AlbertMsg.commands(cmds)

    def _get_cmds(self, config: Config, verbose: bool = False) -> list[str]:
        cmds = set(
            feature["help"]
            for name, feature in self.function_register.items()
            if name in self.activated_functions
            and feature["help"]
            and (not feature["for_geek"] or verbose)
            and not ("sources" in feature.get("commands") and config.albert_mode == "norag")
        )
        return sorted(list(cmds))


# ================================================================================
# Globals lifespan
# ================================================================================

command_registry = CommandRegistry({}, set())
user_configs: dict[str, Config] = defaultdict(lambda: Config())
tiam = TchapIam(Config())


async def log_not_allowed(msg: str, ep: EventParser, matrix_client: MatrixClient):
    """Send feedback message for unauthorized user"""
    config = user_configs[ep.sender]
    await matrix_client.send_markdown_message(ep.room.room_id, msg, msgtype="m.notice")

    # If user is new to the pending list, send a notification for a new pending user
    if await tiam.add_pending_user(config, ep.sender):
        if config.errors_room_id:
            try:
                await matrix_client.send_markdown_message(
                    config.errors_room_id,
                    f"\u26a0\ufe0f **New Albert Tchap user access request**\n\n{ep.sender}\n\nMatrix server: {config.matrix_home_server}",
                )
            except:
                print("Failed to find error room ?!")


# ================================================================================
# Decorators
# ================================================================================


def register_feature(
    group: str,
    onEvent: Event,
    command: str | None = None,
    aliases: list[str] | None = None,
    prefix: str = COMMAND_PREFIX,
    help: str | None = None,
    for_geek: bool = False,
):
    def decorator(func):
        command_registry.add_command(
            name=func.__name__,
            group=group,
            onEvent=onEvent,
            command=command,
            aliases=aliases,
            prefix=prefix,
            help_message=help,
            for_geek=for_geek,
            func=func,
        )
        return func

    return decorator


def only_allowed_user(func):
    """decorator to use with async function using EventParser"""

    @wraps(func)
    async def wrapper(ep: EventParser, matrix_client: MatrixClient):
        ep.do_not_accept_own_message()  # avoid infinite loop
        ep.only_on_direct_message()  # Only in direct room for now (need a spec for "saloon" conversation)

        config = user_configs[ep.sender]
        is_allowed, msg = await tiam.is_user_allowed(config, ep.sender, refresh=True)
        if not is_allowed:
            if not msg or ep.is_command(COMMAND_PREFIX):
                # Only send back the message for the generic albert_answer method
                # ignoring other callbacks.
                raise EventNotConcerned

            await log_not_allowed(msg, ep, matrix_client)
            return

        await func(ep, matrix_client)
        await matrix_client.room_typing(ep.room.room_id, typing_state=False)

    return wrapper


# ================================================================================
# Bot commands
# ================================================================================


@register_feature(
    group="basic",
    onEvent=RoomMessageText,
    command="aide",
    aliases=["help", "aiuto"],
    help=AlbertMsg.shorts["help"],
)
@only_allowed_user
async def help(ep: EventParser, matrix_client: MatrixClient):
    config = user_configs[ep.sender]

    commands = ep.get_command()
    verbose = False
    if len(commands) > 1 and commands[1] in ["-v", "--verbose", "--more", "-a", "--all"]:
        verbose = True
    await matrix_client.send_markdown_message(ep.room.room_id, command_registry.get_help(config, verbose))  # fmt: off


@register_feature(
    group="albert",
    # @DEBUG: RoomCreateEvent is not captured ?
    onEvent=RoomMemberEvent,
    help=None,
)
@only_allowed_user
async def albert_welcome(ep: EventParser, matrix_client: MatrixClient):
    """
    Receive the join/invite event and send the welcome/help message
    """
    config = user_configs[ep.sender]

    ep.only_on_join()

    config.update_last_activity()
    await matrix_client.room_typing(ep.room.room_id)
    await asyncio.sleep(
        3
    )  # wait for the room to be ready - otherwise the encryption seems to be not ready
    await matrix_client.send_markdown_message(ep.room.room_id, command_registry.get_help(config))


@register_feature(
    group="albert",
    onEvent=RoomMessageText,
    command="reset",
    help=AlbertMsg.shorts["reset"],
)
@only_allowed_user
async def albert_reset(ep: EventParser, matrix_client: MatrixClient):
    config = user_configs[ep.sender]
    if config.albert_with_history:
        config.update_last_activity()
        config.albert_history_lookup = 0
        reset_message = AlbertMsg.reset
        # reset_message += command_registry.show_commands(config)
        await matrix_client.send_markdown_message(
            ep.room.room_id, reset_message, msgtype="m.notice"
        )
    else:
        await matrix_client.send_markdown_message(
            ep.room.room_id,
            "Le mode conversation n'est pas activé. tapez !conversation pour l'activer.",
            msgtype="m.notice",
        )


@register_feature(
    group="albert",
    onEvent=RoomMessageText,
    command="conversation",
    help=AlbertMsg.shorts["conversation"],
    for_geek=True,
)
@only_allowed_user
async def albert_conversation(ep: EventParser, matrix_client: MatrixClient):
    config = user_configs[ep.sender]
    config.albert_history_lookup = 0
    if config.albert_with_history:
        config.albert_with_history = False
        message = "Le mode conversation est désactivé."
    else:
        config.update_last_activity()
        config.albert_with_history = True
        message = "Le mode conversation est activé."
    await matrix_client.send_markdown_message(ep.room.room_id, message, msgtype="m.notice")


@register_feature(
    group="albert",
    onEvent=RoomMessageText,
    command="debug",
    help=AlbertMsg.shorts["debug"],
    for_geek=True,
)
@only_allowed_user
async def albert_debug(ep: EventParser, matrix_client: MatrixClient):
    config = user_configs[ep.sender]
    debug_message = AlbertMsg.debug(config)
    await matrix_client.send_markdown_message(ep.room.room_id, debug_message, msgtype="m.notice")


@register_feature(
    group="albert",
    onEvent=RoomMessageText,
    command="model",
    aliases=["models"],
    help=AlbertMsg.shorts["model"],
    for_geek=True,
)
@only_allowed_user
async def albert_model(ep: EventParser, matrix_client: MatrixClient):
    config = user_configs[ep.sender]
    await matrix_client.room_typing(ep.room.room_id)
    command = ep.get_command()
    # Get all available models
    all_models = list(get_available_models(config))
    models_list = "\n\n- " + "\n- ".join(
        map(lambda x: x + (" *" if x == config.albert_model else ""), all_models)
    )
    if len(command) <= 1:
        message = "La commande !model nécessite de donner un modèle parmi :" + models_list
        message += "\n\nExemple: `!model " + all_models[-1] + "`"
    else:
        model = command[1]
        if model not in all_models:
            message = "La commande !model nécessite de donner un modèle parmi :" + models_list
            message += "\n\nExemple: `!model " + all_models[-1] + "`"
        else:
            previous_model = config.albert_model
            config.albert_model = model
            message = f"Le modèle a été modifié : {previous_model} -> {model}"
    await matrix_client.send_markdown_message(ep.room.room_id, message, msgtype="m.notice")


@register_feature(
    group="albert",
    onEvent=RoomMessageText,
    command="mode",
    aliases=["modes"],
    help=AlbertMsg.shorts["mode"],
    for_geek=True,
)
@only_allowed_user
async def albert_mode(ep: EventParser, matrix_client: MatrixClient):
    config = user_configs[ep.sender]
    await matrix_client.room_typing(ep.room.room_id)
    command = ep.get_command()
    # Get all available mode for the current model
    all_modes = get_available_modes(config)
    mode_list = "\n\n- " + "\n- ".join(
        map(lambda x: x + (" *" if x == config.albert_mode else ""), all_modes)
    )
    if len(command) <= 1:
        message = "La commande !mode nécessite de donner un mode parmi :" + mode_list
        message += "\n\nExemple: `!mode " + all_modes[-1] + "`"
    else:
        mode = command[1]
        if mode not in all_modes:
            message = "La commande !mode nécessite de donner un mode parmi :" + mode_list
            message += "\n\nExemple: `!mode " + all_modes[-1] + "`"
        else:
            old_mode = config.albert_mode
            config.albert_mode = mode
            message = f"Le mode a été modifié : {old_mode} -> {mode}"
    await matrix_client.send_markdown_message(ep.room.room_id, message, msgtype="m.notice")


@register_feature(
    group="albert",
    onEvent=RoomMessageText,
    command="sources",
    help=AlbertMsg.shorts["sources"],
)
@only_allowed_user
async def albert_sources(ep: EventParser, matrix_client: MatrixClient):
    config = user_configs[ep.sender]

    try:
        if config.last_rag_sources:
            await matrix_client.room_typing(ep.room.room_id)
            sources = config.last_rag_sources
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
        await matrix_client.send_markdown_message(ep.room.room_id, AlbertMsg.failed, msgtype="m.notice")  # fmt: off
        return

    await matrix_client.send_markdown_message(ep.room.room_id, sources_msg)

@register_feature(
    group="albert",
    onEvent=RoomMessageFile
)
@only_allowed_user
async def albert_document(ep: EventParser, matrix_client: MatrixClient):
    config = user_configs[ep.sender]

    mime_type, _ = mimetypes.guess_type(ep.event.body)
    if mime_type in ['application/json', 'application/pdf', 'application/vnd.openxmlformats-officedocument.wordprocessingml.document']:
        config.update_last_activity()       
        response = (
            f"J'ai détecté que vous avez téléchargé un fichier {mime_type}. "
            "Que souhaitez-vous que je fasse avec ce document ? "
            "Je peux par exemple l'analyser ou répondre à des questions à son sujet."
        )
        await matrix_client.send_markdown_message(ep.room.room_id, response)
    else:
        response = (
            f"J'ai détecté que vous avez téléchargé un fichier {mime_type}. "
            "Ce fichier n'est pris en charge par Albert. "
            "Veuillez téléverser un fichier PDF, DOCX ou JSON."
        )
        await matrix_client.send_markdown_message(ep.room.room_id, response)

@register_feature(
    group="albert",
    onEvent=RoomMessageText,
    help=None,
)
@only_allowed_user
async def albert_answer(ep: EventParser, matrix_client: MatrixClient):
    """
    Receive a message event which is not a command, send the prompt to Albert API and return the response to the user
    """
    config = user_configs[ep.sender]

    initial_history_lookup = config.albert_history_lookup

    user_query = ep.event.body.strip()
    if ep.is_command(COMMAND_PREFIX):
        raise EventNotConcerned

    if config.albert_with_history and config.is_conversation_obsolete:
        config.albert_history_lookup = 0
        obsolescence_in_minutes = str(config.conversation_obsolescence // 60)
        reset_message = AlbertMsg.reset_notif(obsolescence_in_minutes)
        await matrix_client.send_markdown_message(
            ep.room.room_id, reset_message, msgtype="m.notice"
        )

    config.update_last_activity()
    await matrix_client.room_typing(ep.room.room_id)
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

        answer = generate(config, messages)

    except Exception as albert_err:
        logger.error(f"{albert_err}")
        traceback.print_exc()
        # Send an error message to the user
        await matrix_client.send_markdown_message(
            ep.room.room_id, AlbertMsg.failed, msgtype="m.notice"
        )
        # Redirect the error message to the errors room if it exists
        if config.errors_room_id:
            try:
                await matrix_client.send_markdown_message(config.errors_room_id, AlbertMsg.error_debug(albert_err, config))  # fmt: off
            except:
                print("Failed to find error room ?!")

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
        await tiam.increment_user_question(ep.sender)
    except Exception as llm_exception:  # it seems to work when we retry
        logger.error(f"asyncio error when sending message {llm_exception=}. retrying")
        await asyncio.sleep(1)
        try:
            # Try once more
            await matrix_client.send_markdown_message(ep.room.room_id, answer, reply_to=reply_to)
            await tiam.increment_user_question(ep.sender)
        except:
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
    """Special handler to catch invalid command"""
    config = user_configs[ep.sender]

    ep.do_not_accept_own_message()  # avoid infinite loop
    ep.only_on_direct_message()  # Only in direct room for now (need a spec for "saloon" conversation)

    command = ep.event.body.strip().lstrip(COMMAND_PREFIX).split()
    if not ep.is_command(COMMAND_PREFIX):
        # Not a command
        raise EventNotConcerned
    elif command_registry.is_valid_command(command[0]):
        # Valid command
        raise EventNotConcerned

    is_allowed, msg = await tiam.is_user_allowed(config, ep.sender, refresh=True)
    if not is_allowed:
        await log_not_allowed(msg, ep, matrix_client)
        return

    cmds_msg = command_registry.show_commands(config)
    await matrix_client.send_markdown_message(
        ep.room.room_id, AlbertMsg.unknown_command(cmds_msg), msgtype="m.notice"
    )
