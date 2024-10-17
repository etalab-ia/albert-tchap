# SPDX-FileCopyrightText: 2023 Pôle d'Expertise de la Régulation Numérique <contact.peren@finances.gouv.fr>
# SPDX-FileCopyrightText: 2024 Etalab <etalab@modernisation.gouv.fr>
#
# SPDX-License-Identifier: MIT

from typing import Optional
from io import BytesIO

from matrix_bot.eventparser import EventParser
from nio import Event, MatrixRoom, MessageDirection
from nio.crypto.attachments import decrypt_attachment

from bot_msg import AlbertMsg
from config import Config


def has_keys_along(nested_dict: dict, keys: list[str]) -> bool:
    current_level = nested_dict
    for key in keys:
        if isinstance(current_level, dict) and key in current_level:
            current_level = current_level[key]
        else:
            return False
    return True


def isa_reply_to(event) -> bool:
    return has_keys_along(event.source, ["content", "m.relates_to", "m.in_reply_to", "event_id"])


#
# Message management
#


async def get_thread_messages(
    config: Config, ep: EventParser, max_rewind: int = 100
) -> list[Event]:
    matrix_client = ep.matrix_client
    event = ep.event

    # Build the conversation thread
    messages: list = []
    i = 0
    while isa_reply_to(event) and i < max_rewind:
        messages.insert(0, event)
        previous_event_id = event.source["content"]["m.relates_to"]["m.in_reply_to"]["event_id"]
        previous = await matrix_client.room_get_event(ep.room.room_id, previous_event_id)
        event = previous.event
        i += 1

    # Insert the last non original poster message
    if not isa_reply_to(event) and i < max_rewind:
        messages.insert(0, event)

    return messages


async def get_previous_messages(
    config: Config, ep: EventParser, history_lookup: int = 10, max_rewind: int = 100
) -> list[Event]:
    matrix_client = ep.matrix_client
    # Build the conversation history
    starttoken = matrix_client.next_batch
    roommessages = await matrix_client.room_messages(
        ep.room.room_id,
        starttoken,
        limit=min(config.albert_history_lookup, config.albert_max_rewind),
        direction=MessageDirection.back,
        message_filter={"types": ["m.room.message", "m.room.encrypted"]},
    )
    messages: list = []
    decr = 0
    for i, event in enumerate(roommessages.chunk):
        body = event.source["content"]["body"].strip()
        # Or only accept "mesgtype" == m.text ?
        if (
            isa_reply_to(event)
            or event.source["content"]["msgtype"] in ["m.notice"]
            or any(body.startswith(msg) for msg in AlbertMsg.common_msg_prefixes)
        ):
            decr += 1
            continue
        messages.insert(0, event)
        if i - decr >= min(history_lookup, max_rewind):
            break

    return messages


def get_cleanup_body(event: Event) -> str:
    body = event.source["content"]["body"].strip()

    # Remove quoted text in reply to avoid unnecesserilly text
    if body.startswith("> <@"):
        line_start = 0
        lines = body.split("\n")
        for line in lines:
            if line.startswith("> "):
                line_start += 1
            else:
                break
        body = "\n".join(lines[line_start:])

    return body.strip()


async def get_decrypted_file(ep: EventParser) -> BytesIO:
    response = await ep.matrix_client.download(ep.event.url)
    content = decrypt_attachment(
        response.body, 
        ep.event.key.get('k'), 
        ep.event.hashes['sha256'], 
        ep.event.iv
    )
    file = BytesIO(content)
    file.name = ep.event.source['content']['body']
    file.type = ep.event.source['content']['info']['mimetype']
    return file

#
# User management
#

default_power_to_title = {
    0: "utilisateur",
    50: "modérateur",
    100: "administrateur",
}


def user_name_to_non_hl_user(complete_user_name: str) -> str:
    """get the string of the user"""
    return complete_user_name.split("[")[0].strip()


def get_user_to_power_level(salon: MatrixRoom) -> dict:
    users = {user_id: user.name for user_id, user in salon.users.items()}
    return {
        user_name_to_non_hl_user(user_name): salon.power_levels.users.get(user_id, 0)
        for user_id, user_name in users.items()
    }


def get_salon_moderators(
    salon: MatrixRoom, *, fomo_user_name=None, kick_user_name=None
) -> Optional[list[str]]:
    user_to_power_level = get_user_to_power_level(salon)
    if fomo_user_name and fomo_user_name in user_to_power_level.keys():
        return None
    if kick_user_name and kick_user_name not in user_to_power_level.keys():
        return None
    minimum_power_level = 50
    if kick_user_name:
        minimum_power_level = user_to_power_level[kick_user_name] + 1
    return [
        user_name
        for user_name, power_level in user_to_power_level.items()
        if power_level >= minimum_power_level
    ]
