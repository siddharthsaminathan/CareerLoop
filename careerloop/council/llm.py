"""
DeepSeek model routing for Resume Council stages.

ACTIVE — imported by graph.py for all LLM-calling council nodes.
"""

import json
import os
from pathlib import Path
from typing import Any

import requests

try:
    import yaml
except ImportError:
    yaml = None


ROOT = Path(__file__).resolve().parent.parent.parent


def load_council_model_config() -> dict[str, Any]:
    config = {
        "strategy_model": "deepseek-chat",
        "writer_model": "deepseek-chat",
        "temperature": 0.2,
        "max_tokens": 3000,
    }
    config_path = ROOT / "config" / "models.yml"
    if yaml is not None and config_path.exists():
        try:
            data = yaml.safe_load(config_path.read_text(encoding="utf-8")) or {}
            council = data.get("resume_council", {}) or {}
            config.update({k: v for k, v in council.items() if k in config})
        except Exception:
            pass
    config["strategy_model"] = os.getenv("CAREERLOOP_COUNCIL_STRATEGY_MODEL", config["strategy_model"])
    config["writer_model"] = os.getenv("CAREERLOOP_COUNCIL_WRITER_MODEL", config["writer_model"])
    return config


class CouncilLLMClient:
    def __init__(self, model_kind: str = "strategy", api_key: str = None):
        cfg = load_council_model_config()
        self.api_key = api_key or os.getenv("DEEPSEEK_API_KEY", "")
        self.base_url = os.getenv("DEEPSEEK_BASE_URL", "https://api.deepseek.com/v1")
        self.model = cfg["strategy_model"] if model_kind == "strategy" else cfg["writer_model"]
        self.temperature = cfg["temperature"]
        self.max_tokens = cfg["max_tokens"]

    @property
    def available(self) -> bool:
        return bool(self.api_key)

    def complete_json(self, system_prompt: str, user_prompt: str) -> dict[str, Any]:
        if not self.available:
            raise RuntimeError("DEEPSEEK_API_KEY is required for Resume Council LLM stages.")
        response = requests.post(
            f"{self.base_url}/chat/completions",
            headers={
                "Authorization": f"Bearer {self.api_key}",
                "Content-Type": "application/json",
            },
            json={
                "model": self.model,
                "messages": [
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_prompt},
                ],
                "temperature": self.temperature,
                "max_tokens": self.max_tokens,
                "response_format": {"type": "json_object"},
            },
            timeout=90,
        )
        response.raise_for_status()
        content = response.json()["choices"][0]["message"]["content"]
        return json.loads(content)
