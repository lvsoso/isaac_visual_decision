"""Small local HTTP bridge over the checkpoint's official DecisionEngine.predict().

The public boundary accepts image BYTES; a temporary local PNG is used only inside
this process because the official checkpoint engine accepts local image paths.
No chat/generate path or hosted Jev call is involved.
"""
from __future__ import annotations
import base64
import copy
import hashlib
import hmac
import importlib.util
import io
import json
import os
import sys
import tempfile
import threading
import time
import warnings
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from .core import ACTIONS, ProtocolError, parse_decision
from .protocol import MAX_IMAGES, validate_request
from .audit import sha256_file

MAX_BODY = 5 * 1024 * 1024
MAX_PNG = 3 * 1024 * 1024
MAX_PIXELS = 4_000_000


def validate_png(data: str) -> bytes:
    if len(data) > (MAX_PNG * 4 // 3 + 8):
        raise ProtocolError("PNG payload too large")
    try:
        raw = base64.b64decode(data, validate=True)
    except (ValueError, TypeError) as exc:
        raise ProtocolError("Invalid base64") from exc
    if len(raw) > MAX_PNG or not raw.startswith(b"\x89PNG\r\n\x1a\n"):
        raise ProtocolError("Expected a PNG of at most 3 MiB")
    # Use a real decoder, not just a magic-byte check; reject animated/bomb images.
    from PIL import Image
    try:
        with warnings.catch_warnings():
            warnings.simplefilter("error", Image.DecompressionBombWarning)
            with Image.open(io.BytesIO(raw)) as image:
                if image.format != "PNG" or getattr(image, "is_animated", False):
                    raise ProtocolError("Only static PNG is accepted")
                if image.width * image.height > MAX_PIXELS:
                    raise ProtocolError("PNG exceeds 4 million pixels")
                image.verify()
            with Image.open(io.BytesIO(raw)) as image:
                image.load()
    except ProtocolError:
        raise
    except Exception as exc:
        raise ProtocolError(f"Cannot decode PNG: {type(exc).__name__}") from exc
    return raw


class ProcessorAudit:
    """Observe actual processor inputs/output; forward without altering tensors."""
    def __init__(self, processor):
        self.processor = processor
        self.last = None

    def __getattr__(self, name):
        return getattr(self.processor, name)

    def __call__(self, *args, **kwargs):
        if kwargs.get("truncation", False) is not False:
            raise ProtocolError("Image/text processor truncation is forbidden")
        kwargs["truncation"] = False
        images = kwargs.get("images", [])
        rgb_hashes = [hashlib.sha256(image.convert("RGB").tobytes()).hexdigest() for image in images]
        batch = self.processor(*args, **kwargs)
        grid = batch.get("image_grid_thw")
        self.last = {"normalized_rgb_sha256s": rgb_hashes,
                     "image_grid_thw": grid.tolist() if grid is not None else [],
                     "input_tokens": int(batch["input_ids"].shape[-1])}
        return batch


class OfficialEngine:
    def __init__(self, checkpoint: str, *, trust_model_code: bool, expected_sha: str | None = None,
                 device: str = "cuda", dtype: str = "bfloat16", max_length: int = 8192,
                 temperature: float | None = None):
        if not trust_model_code:
            raise ProtocolError("Review checkpoint/inference.py, then explicitly pass --trust-model-code")
        self.checkpoint = Path(checkpoint).expanduser().resolve()
        script = self.checkpoint / "inference.py"
        if not script.is_file() or not (self.checkpoint / "config.json").is_file():
            raise ProtocolError("Download the COMPLETE official checkpoint including inference.py and config.json")
        digest = sha256_file(script)
        if expected_sha and digest != expected_sha:
            raise ProtocolError("inference.py SHA256 does not match --expected-inference-sha256")
        spec = importlib.util.spec_from_file_location("_intern_decision_checkpoint", script)
        if spec is None or spec.loader is None:
            raise ProtocolError("Cannot load checkpoint inference module")
        mod = importlib.util.module_from_spec(spec)
        # dataclasses may resolve annotations via sys.modules during module import.
        sys.modules[spec.name] = mod
        spec.loader.exec_module(mod)
        kwargs = dict(checkpoint=str(self.checkpoint), device=device, dtype=dtype,
                      max_length=max_length, attn_implementation="sdpa")
        if temperature is not None:
            kwargs["temperature"] = temperature
        self.engine = mod.DecisionEngine(**kwargs)
        if not callable(getattr(self.engine, "predict", None)):
            raise ProtocolError("This checkpoint does not expose DecisionEngine.predict(request)")
        self.processor_audit = ProcessorAudit(self.engine.backend.processor)
        self.engine.backend.processor = self.processor_audit
        self.metadata = {"is_mock": False, "checkpoint": str(self.checkpoint),
                         "inference_py_sha256": digest, "config_sha256": sha256_file(self.checkpoint / "config.json"),
                         "device": device, "dtype": dtype, "max_length": max_length,
                          "temperature": getattr(self.engine, "temperature", temperature), "vision_input_audit": True,
                          "model_files_sha256": {name: sha256_file(self.checkpoint/name) for name in
                              ("config.json", "preprocessor_config.json", "processor_config.json", "tokenizer_config.json",
                               "chat_template.jinja", "DOWNLOAD_RECEIPT.json") if (self.checkpoint/name).is_file()}}

    def predict(self, request: dict) -> dict:
        from PIL import Image
        expected = []
        for path in request.get("images", []):
            with Image.open(path) as image:
                expected.append(hashlib.sha256(image.convert("RGB").tobytes()).hexdigest())
        self.processor_audit.last = None
        result = self.engine.predict(request)
        audit = self.processor_audit.last
        if expected:
            if not audit or audit["normalized_rgb_sha256s"] != expected or len(audit["image_grid_thw"]) != len(expected):
                raise ProtocolError("Official processor image count/order does not match the request")
            if audit["input_tokens"] > self.metadata["max_length"]:
                raise ProtocolError("Official processor input exceeds the non-truncating length limit")
            result["_vision_audit"] = copy.deepcopy(audit)
        return result


class MockEngine:
    """Contract test fixture only: does NOT interpret the image or run any model."""
    metadata = {"is_mock": True, "checkpoint": None, "model": "MOCK-NOT-A-MODEL"}

    def predict(self, request: dict) -> dict:
        previous = request["state"].get("previous_action")
        if previous in ACTIONS[:-2]:
            choice = ACTIONS[ACTIONS.index(previous) + 1]
        elif previous == "release":
            choice = "abort"
        else:
            choice = "pre_grasp"
        return {"model": "MOCK-NOT-A-MODEL", "answers": {"next_stage": {
            "type": "choice", "choice": choice, "decision": choice,
            "probabilities": {k: float(k == choice) for k in ACTIONS}, "confidence": 1.0}},
            "usage": {"input_tokens": 0, "output_tokens": 0}}


class DecisionBridge:
    def __init__(self, engine, token: str | None = None):
        self.engine = engine
        self.token = token
        self.lock = threading.Lock()
        self.started = time.monotonic()
        self.requests_completed = 0
        self.source_hashes = {"bridge_source_sha256": sha256_file(Path(__file__)),
                              "protocol_source_sha256": sha256_file(Path(__file__).with_name("protocol.py"))}

    def health(self) -> dict:
        return {"status": "ok", "bridge_schema": 1, "supports_images": True, "max_images": MAX_IMAGES,
                "busy": self.lock.locked(), "requests_completed": self.requests_completed,
                "uptime_seconds": round(time.monotonic() - self.started, 3), **self.source_hashes, **self.engine.metadata}

    def predict(self, request: dict) -> dict:
        validate_request(request)
        images = [validate_png(item["data"]) for item in request["images"]]
        if not self.lock.acquire(blocking=False):
            raise BlockingIOError("GPU is busy; one request is allowed at a time")
        try:
            # Temporary path is server-generated. A client filename never becomes a path.
            with tempfile.TemporaryDirectory(prefix="visual-decision-") as directory:
                paths = []
                for index, raw in enumerate(images):
                    image_path = Path(directory) / f"observation_{index}.png"
                    image_path.write_bytes(raw)
                    paths.append(str(image_path))
                internal = copy.deepcopy(request)
                internal["images"] = paths
                start = time.perf_counter()
                result = self.engine.predict(internal)
                if not isinstance(result, dict):
                    raise ProtocolError("Official engine did not return a dict")
                result = copy.deepcopy(result)
                result["_bridge"] = {"bridge_schema": 1, "is_mock": self.engine.metadata["is_mock"],
                    "image_sha256": hashlib.sha256(images[0]).hexdigest(),
                    "image_sha256s": [hashlib.sha256(raw).hexdigest() for raw in images],
                    "image_count": len(images), "inference_py_sha256": self.engine.metadata.get("inference_py_sha256"),
                    "engine_ms": (time.perf_counter() - start) * 1000}
                parse_decision(result, allow_mock=True)
                json.dumps(result, allow_nan=False)
                self.requests_completed += 1
                return result
        finally:
            self.lock.release()


def make_http_server(host: str, port: int, bridge: DecisionBridge) -> ThreadingHTTPServer:
    class Handler(BaseHTTPRequestHandler):
        protocol_version = "HTTP/1.1"
        server_version = "VisualDecisionBridge/0.1"

        def setup(self):
            super().setup()
            self.connection.settimeout(30)

        def log_message(self, *args):
            pass  # no prompts, paths, images or credentials in access logs

        def send_json(self, status: int, obj: dict):
            body = json.dumps(obj, ensure_ascii=False, allow_nan=False).encode("utf-8")
            self.send_response(status)
            self.send_header("Content-Type", "application/json; charset=utf-8")
            self.send_header("Content-Length", str(len(body)))
            self.send_header("Cache-Control", "no-store")
            self.send_header("Connection", "close")
            self.end_headers()
            self.close_connection = True
            try:
                self.wfile.write(body)
            except (BrokenPipeError, ConnectionResetError):
                pass  # client timeout does not undo a completed forward pass

        def authorized(self) -> bool:
            if bridge.token and not hmac.compare_digest(self.headers.get("Authorization", ""), "Bearer " + bridge.token):
                self.send_json(401, {"error": "Unauthorized"})
                return False
            return True

        def do_GET(self):
            if not self.authorized():
                return
            if self.path == "/health":
                self.send_json(200, bridge.health())
            else:
                self.send_json(404, {"error": "Routes: GET /health; POST /v1/decisions. This is not a chat server."})

        def do_POST(self):
            if not self.authorized():
                return
            if self.path != "/v1/decisions":
                self.send_json(404, {"error": "Unknown route"})
                return
            if self.headers.get("Transfer-Encoding"):
                self.send_json(400, {"error": "Chunked requests are not supported"})
                return
            if self.headers.get_content_type() != "application/json":
                self.send_json(415, {"error": "Use Content-Type: application/json"})
                return
            try:
                length = int(self.headers.get("Content-Length", "0"))
            except ValueError:
                length = 0
            if length <= 0 or length > MAX_BODY:
                self.send_json(413, {"error": "Request must be 1 byte to 5 MiB"})
                return
            try:
                data = self.rfile.read(length)
                if len(data) != length:
                    raise ProtocolError("Incomplete request body")
                request = json.loads(data)
                result = bridge.predict(request)
                self.send_json(200, result)
            except BlockingIOError:
                self.send_json(503, {"error": "Model busy; no automatic retry performed"})
            except (ProtocolError, ValueError, UnicodeDecodeError, TypeError) as exc:
                self.send_json(422, {"error": str(exc)[:1000]})
            except Exception as exc:
                # error class/message is useful; no traceback with input material is returned
                self.send_json(500, {"error": f"{type(exc).__name__}: {str(exc)[:1000]}"})
    server = ThreadingHTTPServer((host, port), Handler)
    server.daemon_threads = True
    return server
