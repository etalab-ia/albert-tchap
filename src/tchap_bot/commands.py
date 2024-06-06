# SPDX-FileCopyrightText: 2023 Pôle d'Expertise de la Régulation Numérique <contact.peren@finances.gouv.fr>
#
# SPDX-License-Identifier: MIT

import datetime
from dataclasses import dataclass

from nio import MatrixRoom, Event

from matrix_bot.callbacks import properly_fail
from matrix_bot.client import MatrixClient
from matrix_bot.config import logger
from matrix_bot.eventparser import MessageEventParser, ignore_when_not_concerned
from .tchap_utils import get_salon_moderators, user_name_to_non_hl_user, users_print
from .config import env_config


if env_config.llm.llm_active:
    from llama_index.llms import Ollama

    llm_model = Ollama(base_url=env_config.llm.ollama_address, model=env_config.llm.model)


@dataclass
class CommandRegistry:
    function_register: dict
    activated_functions: set[str]

    def add_command(self, *, name: str, help_message: str, group: str, func):
        self.function_register[name] = {"help": help_message, "group": group, "func": func}

    def get_help(self) -> list[str]:
        return [
            function["help"] for name, function in self.function_register.items() if name in self.activated_functions
        ]

    def activate_and_retrieve_group(self, group_name: str):
        self.activated_functions |= {
            name for name, function in self.function_register.items() if function["group"] == group_name
        }
        return [
            function["func"] for name, function in self.function_register.items() if function["group"] == group_name
        ]


command_registry = CommandRegistry({}, set())


def register_feature(help: str, group: str):  # pylint: disable=redefined-builtin
    def decorator(func):
        command_registry.add_command(name=func.__name__, help_message=help, group=group, func=func)
        return func

    return decorator


@register_feature(help="**!help** : donne l'aide", group="basic")
@properly_fail
@ignore_when_not_concerned
async def bot_help(room: MatrixRoom, message: Event, matrix_client: MatrixClient):
    event_parser = MessageEventParser(room=room, event=message, matrix_client=matrix_client)
    event_parser.do_not_accept_own_message()
    help_message = "les commandes sont :\n - " + "\n - ".join(command_registry.get_help())
    event_parser.command("help")
    logger.info("Handling command", command="help")
    await matrix_client.room_typing(room.room_id)
    await matrix_client.send_markdown_message(room.room_id, help_message)


@register_feature(help="**!heure**: donne l'heure", group="basic")
@properly_fail
@ignore_when_not_concerned
async def heure(room: MatrixRoom, message: Event, matrix_client: MatrixClient):
    event_parser = MessageEventParser(room=room, event=message, matrix_client=matrix_client)
    event_parser.do_not_accept_own_message()
    event_parser.command("heure")
    heure = f"il est {datetime.datetime.now().strftime('%Hh%M')}"
    logger.info("Handling command", command="heure")
    await matrix_client.room_typing(room.room_id)
    await matrix_client.send_text_message(room.room_id, heure)


@register_feature(
    help=(
        "**!fomo [user]**: *Fear Of Missing Out*. "
        "Donne la liste des salons où l'[user] n'est pas. Si user n'est pas précisé c'est soi-même"
    ),
    group="room_utils",
)
@properly_fail
@ignore_when_not_concerned
async def fomo(room: MatrixRoom, message: Event, matrix_client: MatrixClient):
    """fomo : Fear Of Missing Out. List the channels where the user isn't"""
    event_parser = MessageEventParser(room=room, event=message, matrix_client=matrix_client, log_usage=True)
    event_parser.do_not_accept_own_message()
    missing_out_user = user_name_to_non_hl_user(event_parser.command("fomo").strip() or event_parser.sender_username())
    salons = matrix_client.get_non_private_rooms()
    missing_out_salons = {
        salon_item.name: get_salon_moderators(salon_item, fomo_user_name=missing_out_user)
        for salon_item in salons.values()
    }
    text = f"Les salons **géniaux** que {missing_out_user} loupe sont :\n - " + "\n - ".join(
        [
            f"{salon_name} : demande à {users_print(salon_moderators)}"
            for salon_name, salon_moderators in missing_out_salons.items()
            if salon_moderators is not None
        ]
    )
    await matrix_client.send_markdown_message(room.room_id, text)


@register_feature(
    help=(
        "**!kick [user]**: Donne la liste des salons où l'utilisateur est, "
        "ainsi que la liste des gens pouvant l'expulser"
    ),
    group="room_utils",
)
@properly_fail
@ignore_when_not_concerned
async def kick(room: MatrixRoom, message: Event, matrix_client: MatrixClient):
    event_parser = MessageEventParser(room=room, event=message, matrix_client=matrix_client, log_usage=True)
    event_parser.do_not_accept_own_message()
    maybe_user_name = user_name_to_non_hl_user(event_parser.command("kick").strip() or event_parser.sender_username())

    salons = matrix_client.get_non_private_rooms()
    kick_out_salons = {
        salon_item.name: get_salon_moderators(salon_item, kick_user_name=maybe_user_name)
        for salon_item in salons.values()
    }
    maybe_user_name = f"**{maybe_user_name}**"
    text = f"Pour expulser {maybe_user_name} :\n - " + "\n - ".join(
        [
            f"{salon_name} : demande à {users_print(salon_moderators) or maybe_user_name}"
            for salon_name, salon_moderators in kick_out_salons.items()
            if salon_moderators is not None
        ]
    )
    await matrix_client.send_markdown_message(room.room_id, text)


@register_feature(
    help="**@[bot_name] [prompt]**: renvoie la réponse d'un llm au prompt donné",
    group="chatbot",
)
@properly_fail
@ignore_when_not_concerned
async def bot_tchap(room: MatrixRoom, message: Event, matrix_client: MatrixClient):
    event_parser = MessageEventParser(room=room, event=message, matrix_client=matrix_client, log_usage=True)
    event_parser.do_not_accept_own_message()
    prompt = await event_parser.hl()
    await matrix_client.room_typing(room.room_id, typing_state=True, timeout=180_000)
    if env_config.llm.llm_active:
        llm_response = str(llm_model.complete(env_config.llm.pre_prompt + prompt))
    else:
        llm_response = "this is a nice prompt but there is no llm here"
    logger.info(f"{llm_response=}")
    try:  # sometimes the async code fail (when input is big) with random asyncio errors
        await matrix_client.send_text_message(room.room_id, llm_response)
    except Exception as llm_exception:  # it seems to work when we retry
        logger.warning(f"llm response failed with {llm_exception=}. retrying")
        await matrix_client.send_text_message(room.room_id, llm_response)
