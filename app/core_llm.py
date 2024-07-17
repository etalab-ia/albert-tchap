# SPDX-FileCopyrightText: 2024 Etalab <etalab@modernisation.gouv.fr>
#
# SPDX-License-Identifier: MIT

import requests
from pyalbert.clients import LlmClient
from pyalbert.utils import log_and_raise_for_status

from config import Config

# FIX/FUTURE: with pyalbert v0.7 ?
API_PREFIX_V1 = "/api"
API_PREFIX_V2 = "/api/v2"


def get_available_models(config: Config) -> dict:
    """Fetch available models"""
    api_key = config.albert_api_token
    url = config.albert_api_url + API_PREFIX_V2
    headers = {"Authorization": f"Bearer {api_key}"}
    response = requests.get(f"{url}/models", headers=headers)
    log_and_raise_for_status(response)
    model_prompts = response.json()
    return model_prompts or {}


def get_available_modes(config: Config) -> list[str]:
    """Fetch available modes for the current model"""
    model = config.albert_model
    model_prompts = get_available_models(config)
    model_config = model_prompts.get(model, {})
    if not model_config:
        return []

    modes = [x["mode"] for x in model_config.get("prompts", []) if "mode" in x]
    return modes


def generate_sources(config: Config, rag_references: list[str]) -> list[dict]:
    """Fetch chunks sources from references"""
    api_key = config.albert_api_token
    url = config.albert_api_url + API_PREFIX_V2
    headers = {"Authorization": f"Bearer {api_key}"}
    data = {"uids": rag_references}
    response = requests.post(f"{url}/get_chunks", headers=headers, json=data)
    log_and_raise_for_status(response)
    sources = response.json()
    return sources


def generate(config: Config, messages: list, limit=7) -> str:
    api_key = config.albert_api_token
    url = config.albert_api_url + API_PREFIX_V1
    model = config.albert_model
    mode = None if config.albert_mode == "norag" else config.albert_mode
    if not config.albert_with_history:
        messages = messages[-1:]

    # Query LLM API
    # --
    rag_params = {"strategy": "last", "mode": mode, "limit": 7}
    aclient = LlmClient(model, base_url=url, api_key=api_key)
    result = aclient.generate(messages=messages, rag=rag_params)
    answer = result.choices[0].message.content
    if hasattr(result, "rag_context"):
        config.last_rag_references = result.rag_context[0].references

    return answer
