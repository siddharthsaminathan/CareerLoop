"""
DeepSeek model routing for Resume Council stages.

ACTIVE — imported by graph.py for all LLM-calling council nodes.
"""

import json
import os
from pathlib import Path
from typing import Any, Optional

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
        "max_tokens": 4000,
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

    def complete_json(self, system_prompt: str, user_prompt: str,
                       max_tokens: int = None) -> dict[str, Any]:
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
                "max_tokens": max_tokens or self.max_tokens,
                "response_format": {"type": "json_object"},
            },
            timeout=90,
        )
        response.raise_for_status()
        content = response.json()["choices"][0]["message"]["content"]

        # Try direct parse first
        try:
            return json.loads(content)
        except json.JSONDecodeError as e:
            import logging
            logging.warning(f"JSON parse error at char {e.pos}: {e.msg}. Attempting repair...")

        # Repair: try to close unclosed strings/brackets
        print(f"  !! JSON repair fired — LLM output was truncated or malformed ({len(content)} chars)")
        repaired = self._repair_truncated_json(content)
        if repaired is not None:
            print(f"  !! JSON repair succeeded — payload may be incomplete, check output carefully")
            return repaired

        # Last resort: fail hard to trigger retries upstream
        print(f"  !! JSON repair failed — raising exception")
        raise RuntimeError(f"Unrecoverable JSON from LLM: {content[:100]}...")

    @staticmethod
    def _repair_truncated_json(text: str) -> Optional[dict]:
        """Attempt to repair truncated JSON by closing brackets and strings."""
        import re

        # Count brackets
        open_braces = text.count("{") - text.count("}")
        open_brackets = text.count("[") - text.count("]")

        # If we have unclosed string, add closing quote
        in_string = False
        repaired = list(text)
        for i, ch in enumerate(text):
            if ch == '"' and (i == 0 or text[i-1] != '\\\\'):
                in_string = not in_string

        if in_string:
            repaired.append('"')

        # Close remaining brackets
        text2 = "".join(repaired)
        text2 += "]" * open_brackets
        text2 += "}" * open_braces

        try:
            return json.loads(text2)
        except json.JSONDecodeError:
            return None

    @staticmethod
    def _extract_partial_json(text: str) -> dict:
        """Extract whatever valid JSON we can from a broken response."""
        import re

        result = {}

        # Try to extract top-level key-value pairs with regex
        # Match "key": "value" or "key": [...] or "key": {...}
        pairs = re.findall(
            r'"(\\w+)":\s*("(?:[^"\\\\]|\\\\.)*"|\\[[^\\]]*\\]|\\{[^{}]*\\}|\\d+\\.?\\d*)',
            text
        )
        for key, value in pairs:
            try:
                result[key] = json.loads(value)
            except (json.JSONDecodeError, TypeError):
                result[key] = value.strip('"')

        if not result:
            # Absolute fallback: return empty dict with error note
            result["_parse_error"] = True
            result["_raw_preview"] = text[:200]

        return result
