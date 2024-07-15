# SPDX-FileCopyrightText: 2024 Etalab <etalab@modernisation.gouv.fr>
#
# SPDX-License-Identifier: MIT

import json

import requests
from config import Config
from matrix_bot.config import logger
from pyalbert.utils import log_and_raise_for_status


def get_available_models(config: Config) -> list[str] | None:
    api_token = config.albert_api_token
    url = config.albert_api_url
    headers = {"Authorization": f"Bearer {api_token}"}
    response = requests.get(f"{url}/models", headers=headers)
    log_and_raise_for_status(response)
    model_prompts = response.json()
    return list(model_prompts.keys())


def get_available_modes(config: Config) -> list[str] | None:
    model = config.albert_model_name
    model_prompts = get_available_models(config)
    model_config = model_prompts.get(model, {})
    if not model_config:
        return None

    modes = [x["mode"] for x in model_config.get("config", {}).get("prompts", []) if "mode" in x]
    return modes


def generate_sources(config: Config, stream_id: int) -> list[dict]:
    api_token = config.albert_api_token
    api_url = config.albert_api_url

    # Create Stream:
    headers = {"Authorization": f"Bearer {api_token}"}
    response = requests.get(f"{api_url}/stream/{stream_id}", headers=headers)
    log_and_raise_for_status(response)
    stream = response.json()

    # Fetch chunks sources
    if not stream.get("rag_sources"):
        return []
    data = {"uids": stream["rag_sources"]}
    response = requests.post(f"{api_url}/get_chunks", headers=headers, json=data)
    log_and_raise_for_status(response)
    sources = response.json()
    return sources


def generate(config: Config, messages: list, limit=7) -> str:
    api_key = config.albert_api_token
    model = config.albert_model_name
    mode = None if config.albert_mode == "norag" else config.albert_mode
    api_url = config.albert_api_url
    if not config.albert_with_history:
        messages = messages[-1:]

    # Build RAG prompt
    prompter = get_prompter(model, mode)
    messages = prompter.make_prompt(limit=limit, history=messages)

    # Query LLM API
    sampling_params = prompter.get_upstream_sampling_params()
    #llm_client = LlmClient(model=model, base_url=api_url, api_key=api_key)
    llm_client = LlmClient(model=model, base_url=api_url, api_key=api_key)
    result = llm_client.generate(messages, **sampling_params)
    answer = result.choices[0].message.content
    return answer
