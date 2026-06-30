from __future__ import annotations

import json
import os
import urllib.error
import urllib.request


OPENAI_BASE_URL = "https://api.openai.com/v1"


class OpenAIClient:
    def __init__(self, api_key: str | None = None, model: str | None = None) -> None:
        self.api_key = api_key or os.getenv("OPENAI_API_KEY", "")
        self.model = model or os.getenv("OPENAI_MODEL", "gpt-5.4-mini")

    @property
    def enabled(self) -> bool:
        return bool(self.api_key)

    def responses_json(
        self,
        *,
        system: str,
        user: str,
        schema: dict,
        schema_name: str,
        model: str | None = None,
        tools: list[dict] | None = None,
    ) -> tuple[dict, str | None]:
        payload: dict = {
            "model": model or self.model,
            "input": [
                {"role": "system", "content": system},
                {"role": "user", "content": user},
            ],
            "text": {
                "format": {
                    "type": "json_schema",
                    "name": schema_name,
                    "strict": True,
                    "schema": schema,
                }
            },
        }
        if tools:
            payload["tools"] = tools
        response = self.request("/responses", method="POST", payload=payload)
        output = self.extract_output_text(response)
        return json.loads(output), response.get("id")

    def request(self, endpoint: str, *, method: str = "GET", payload: dict | None = None) -> dict:
        if not self.api_key:
            raise RuntimeError("Falta OPENAI_API_KEY")
        data = None
        headers = {"authorization": f"Bearer {self.api_key}"}
        if payload is not None:
            data = json.dumps(payload, ensure_ascii=False).encode("utf-8")
            headers["content-type"] = "application/json"
        req = urllib.request.Request(f"{OPENAI_BASE_URL}{endpoint}", data=data, headers=headers, method=method)
        opener = urllib.request.build_opener(urllib.request.ProxyHandler({}))
        try:
            with opener.open(req, timeout=180) as response:
                raw = response.read().decode("utf-8", errors="replace")
                return json.loads(raw) if raw else {}
        except urllib.error.HTTPError as exc:
            raw = exc.read().decode("utf-8", errors="replace")
            try:
                parsed = json.loads(raw)
                message = parsed.get("error", {}).get("message") or raw
            except Exception:
                message = raw
            raise RuntimeError(message) from exc

    @staticmethod
    def extract_output_text(response: dict) -> str:
        if isinstance(response.get("output_text"), str):
            return response["output_text"]
        chunks: list[str] = []
        for item in response.get("output", []):
            if item.get("type") == "message":
                for content in item.get("content", []):
                    if isinstance(content.get("text"), str):
                        chunks.append(content["text"])
                    if isinstance(content.get("output_text"), str):
                        chunks.append(content["output_text"])
        return "\n".join(chunks).strip()
