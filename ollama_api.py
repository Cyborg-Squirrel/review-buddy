"""An API class for interacting with Ollama"""

# ------------------------------
# Rationale for disabled lints
# ------------------------------
# too-few-public-methods: PyLint flags model type classes with less than
# two public functions. This seems like a bad idea for a linter rule.
#pylint: disable=too-few-public-methods

import json
from dataclasses import dataclass
from typing import Optional

import requests


@dataclass
class OllamaConfig:
    """Ollama config"""
    host: str
    default_model: str

class OllamaApi:
    """API for interacting with Ollama"""

    __API_PATH_GENERATE = "/api/generate"
    __config: OllamaConfig

    def __init__(self, config):
        self.__config = config

    def __do_streaming_request(self, url: str, request: dict) -> str:
        """Makes a request to Ollama with stream set to true, handles streamed response chunks"""
        # Five minute timeout for the request
        req_timeout = 60 * 5
        response = ""
        with requests.post(url,
                           data=json.dumps(request),
                           stream=True,
                           timeout=req_timeout) as r:
            r.raise_for_status()
            for line in r.iter_lines():
                if line:
                    chunk = json.loads(line)
                    done = chunk["done"]
                    response += chunk["response"]
                    if done:
                        break

        return response

    def do_generation(self, request: str, model: Optional[str] = None):
        """Requests a text generation"""
        model_name = model if model is not None else self.__config.default_model
        generate_api_url = f"{self.__config.host}{self.__API_PATH_GENERATE}"
        payload = {
            "model": model_name,
            "prompt": request,
            "stream": True
        }

        return self.__do_streaming_request(generate_api_url, payload)
