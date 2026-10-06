import base64
import copy
import json
import threading
import unittest
from pathlib import Path
from visual_lab.server import *
from visual_lab.client import DecisionClient, ModelAPIError
from visual_lab.protocol import make_request
from visual_lab.png import encode_rgb_bytes

class BridgeTests(unittest.TestCase):
    def setUp(self):
        self.engine = MockEngine()
        self.bridge = DecisionBridge(self.engine)
        self.server = make_http_server("127.0.0.1",0,self.bridge)
        self.thread = threading.Thread(target=self.server.serve_forever,daemon=True)
        self.thread.start()
        self.client = DecisionClient(f"http://127.0.0.1:{self.server.server_port}/v1/decisions",timeout=3)
        self.png = encode_rgb_bytes(4,3,bytes([255,0,0]*12))
        self.request = make_request(self.png,{"previous_action":None})
    def tearDown(self):
        self.server.shutdown()
        self.server.server_close()
        self.thread.join(2)
    def test_health_rejects_mock(self):
        with self.assertRaises(ProtocolError): self.client.health()
    def test_health_mock_explicit(self):
        self.assertTrue(self.client.health(allow_mock=True)["is_mock"])
    def test_http_round_trip_image_hash(self):
        raw, elapsed = self.client.predict(self.request)
        self.assertEqual(raw["_bridge"]["image_sha256"],hashlib.sha256(self.png).hexdigest())
        self.assertEqual(raw["answers"]["next_stage"]["choice"],"pre_grasp")
        self.assertGreater(elapsed,0)
    def test_temp_png_exists_only_during_inference(self):
        paths=[]
        engine=self.engine
        def predict(request):
            paths.extend(request["images"])
            self.assertEqual(Path(paths[0]).read_bytes(),self.png)
            return engine.predict(request)
        class E:
            metadata={"is_mock":True}
        e=E(); e.predict=predict
        self.bridge.engine=e
        original=copy.deepcopy(self.request)
        self.client.predict(self.request)
        self.assertFalse(Path(paths[0]).exists())
        self.assertEqual(original,self.request)
    def test_invalid_base64_422(self):
        self.request["images"][0]["data"]="%%%"
        with self.assertRaisesRegex(ModelAPIError,"422"): self.client.predict(self.request)
    def test_non_png_422(self):
        self.request["images"][0]["data"]=base64.b64encode(b"notPNG").decode()
        with self.assertRaisesRegex(ModelAPIError,"422"): self.client.predict(self.request)
    def test_truncated_png_422(self):
        self.request["images"][0]["data"]=base64.b64encode(self.png[:20]).decode()
        with self.assertRaisesRegex(ModelAPIError,"422"): self.client.predict(self.request)
    def test_lock_busy_503(self):
        self.bridge.lock.acquire()
        try:
            with self.assertRaisesRegex(ModelAPIError,"503"): self.client.predict(self.request)
        finally: self.bridge.lock.release()
    def test_auth_401(self):
        self.bridge.token="test-secret"
        with self.assertRaisesRegex(ModelAPIError,"401"): self.client.health(allow_mock=True)
    def test_auth_correct(self):
        self.bridge.token="test-secret"; self.client.token="test-secret"
        self.assertEqual(self.client.health(allow_mock=True)["status"],"ok")
    def test_engine_failure_500_not_fallback(self):
        class Broken:
            metadata={"is_mock":False}
            def predict(self,request): raise RuntimeError("fake GPU failure")
        self.bridge.engine=Broken()
        with self.assertRaisesRegex(ModelAPIError,"500"): self.client.predict(self.request)
        self.assertEqual(self.bridge.requests_completed,0)
    def test_official_engine_requires_explicit_trust(self):
        with self.assertRaisesRegex(ProtocolError,"trust-model-code"):
            OfficialEngine("/nonexistent",trust_model_code=False)
    def test_client_rejects_chat_endpoint(self):
        with self.assertRaises(ProtocolError):
            DecisionClient("http://127.0.0.1:8000/v1/chat/completions")

if __name__ == "__main__": unittest.main()
