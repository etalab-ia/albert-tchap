# SPDX-FileCopyrightText: 2023 Pôle d'Expertise de la Régulation Numérique <contact.peren@finances.gouv.fr>
#
# SPDX-License-Identifier: MIT

# This file is automatically imported by all tests.
# Add your global fixtures here


def pytest_sessionfinish(session, exitstatus):
    """
    Remove errors when no tests where collected.

    See https://github.com/pytest-dev/pytest/issues/2393#issuecomment-452634365.
    """
    if exitstatus == 5:
        session.exitstatus = 0
