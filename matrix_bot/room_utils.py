# SPDX-FileCopyrightText: 2023 Pôle d'Expertise de la Régulation Numérique <contact.peren@finances.gouv.fr>
#
# SPDX-License-Identifier: MIT

from nio import MatrixRoom

default_power_to_title = {
    0: "utilisateur",
    50: "modérateur",
    100: "administrateur",
}


def room_is_direct_message(room: MatrixRoom) -> bool:
    """Returns True if the room is a direct message room"""
    return len(room.users) == 2
