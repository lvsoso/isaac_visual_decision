"""Standard-library HTTP client; no torch/transformers dependency in Isaac Python."""
from __future__ import annotations
import json
import os
import time
import urllib.error
import urllib.parse
import urllib.request
from .core import LabError, ProtocolError

MAX_RESPONSE_BYTES = 2 * 1024 * 1024

class ModelAPIError(LabError):
    pass

class DecisionClient:
    def __init__(self, endpoint: str, timeout: float = 180, token: str | None = None):
        parts = urllib.parse.urlparse(endpoint)
        if parts.scheme not in {"http", "https"} or not parts.hostname or parts.username or parts.password or parts.query or parts.fragment:
            raise ProtocolError("Use an http(s) endpoint without embedded credentials/query/fragment")
        if parts.path != "/v1/decisions":
            raise ProtocolError("Expected bridge path /v1/decisions")
        if timeout <= 0:
            raise ProtocolError("HTTP timeout must be positive")
        self.endpoint = endpoint
        self.health_url = urllib.parse.urlunparse((parts.scheme, parts.netloc, "/health", "", "", ""))
        self.timeout = timeout
        self.token = token if token is not None else os.getenv("DECISION_API_TOKEN")
        # 不经系统 HTTP_PROXY 发送本地图片；SSH 隧道/明确 HTTPS 地址仍可用。
        self.opener = urllib.request.build_opener(urllib.request.ProxyHandler({}))

    def _request(self, url: str, data: dict | None = None) -> dict:
        headers = {"Accept": "application/json"}
        if self.token:
            headers["Authorization"] = f"Bearer {self.token}"
        payload = None
        if data is not None:
            payload = json.dumps(data, ensure_ascii=False, allow_nan=False).encode("utf-8")
            headers["Content-Type"] = "application/json"
        request = urllib.request.Request(url, data=payload, headers=headers)
        try:
            with self.opener.open(request, timeout=self.timeout) as response:
                raw = response.read(MAX_RESPONSE_BYTES + 1)
                if len(raw) > MAX_RESPONSE_BYTES:
                    raise ModelAPIError("Response exceeds 2 MiB")
        except urllib.error.HTTPError as exc:
            detail = exc.read(4096).decode("utf-8", errors="replace")
            raise ModelAPIError(f"Model HTTP {exc.code}: {detail}") from exc
        except (urllib.error.URLError, TimeoutError, OSError) as exc:
            raise ModelAPIError(f"Model request failed: {exc}") from exc
        try:
            result = json.loads(raw)
        except (json.JSONDecodeError, UnicodeDecodeError) as exc:
            raise ModelAPIError("Model returned invalid JSON") from exc
        if not isinstance(result, dict):
            raise ModelAPIError("Model response is not an object")
        return result

    def health(self, *, allow_mock: bool = False) -> dict:
        result = self._request(self.health_url)
        if result.get("status") != "ok" or result.get("bridge_schema") != 1:
            raise ProtocolError("Expected this kit's healthy bridge (bridge_schema=1), not a chat/vLLM endpoint")
        if result.get("is_mock") and not allow_mock:
            raise ProtocolError("A MOCK service is running; real visual/shadow modes refuse it")
        if not result.get("supports_images"):
            raise ProtocolError("Backend does not declare image support")
        return result

    def predict(self, request: dict) -> tuple[dict, float]:
        start = time.perf_counter()
        response = self._request(self.endpoint, request)
        return response, (time.perf_counter() - start) * 1000
