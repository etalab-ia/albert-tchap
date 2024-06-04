# SPDX-FileCopyrightText: 2023 Pôle d'Expertise de la Régulation Numérique <contact.peren@finances.gouv.fr>
# SPDX-FileCopyrightText: 2024 Etalab <etalab@modernisation.gouv.fr>
#
# SPDX-License-Identifier: MIT

from collections import defaultdict
from typing import Optional

from nio import MatrixRoom

default_power_to_title = {
    0: "utilisateur",
    50: "modérateur",
    100: "administrateur",
}


def get_user_to_power_level(salon: MatrixRoom):
    users = {user_id: user.name for user_id, user in salon.users.items()}
    return {
        user_name_to_non_hl_user(user_name): salon.power_levels.users.get(user_id, 0)
        for user_id, user_name in users.items()
    }


def get_salon_users_str(salon: MatrixRoom):
    user_to_power_level = get_user_to_power_level(salon)
    user_to_print = defaultdict(list)
    for user_name, power_level in user_to_power_level.items():
        key = default_power_to_title.get(power_level, "utilisateur")
        # remove the originating server to remove the highlight
        user_to_print[key] += [user_name]
    return "\n".join(f" - **{key}** : {','.join(value) } " for key, value in user_to_print.items())


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


def user_name_to_non_hl_user(complete_user_name: str) -> str:
    """get the string of the user"""
    return complete_user_name.split("[")[0].strip()


def users_print(matrix_user_name: list[str]) -> str:
    """Print a list of user without highlighting them in the tchap case"""
    return ", ".join(user_name for user_name in matrix_user_name)
