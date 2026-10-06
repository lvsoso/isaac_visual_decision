"""CPU/HTTP input contracts; does not prove GPU image understanding."""
import base64
import copy
import hashlib
import unittest
from pathlib import Path

from tests import test_bridge
from visual_lab.core import ProtocolError
from visual_lab.protocol import validate_request


class MultiViewBridgeTests(test_bridge.BridgeTests):
    def two_images(self):
        from visual_lab.png import encode_rgb_bytes
        other = encode_rgb_bytes(4, 3, bytes([0, 255, 0]*12))
        request = copy.deepcopy(self.request)
        request['images'].append({'type': 'image/png', 'data': base64.b64encode(other).decode()})
        return request, other

    def test_two_images_are_processed_in_order_and_cleaned(self):
        request, other = self.two_images()
        original = copy.deepcopy(request)
        paths = []
        engine = self.engine
        def predict(internal):
            paths.extend(internal['images'])
            self.assertEqual([Path(path).read_bytes() for path in paths], [self.png, other])
            return engine.predict(internal)
        self.bridge.engine = type('E', (), {'metadata': {'is_mock': True}, 'predict': staticmethod(predict)})()
        raw, _ = self.client.predict(request)
        self.assertEqual(raw['_bridge']['image_count'], 2)
        self.assertEqual(raw['_bridge']['image_sha256s'], [hashlib.sha256(data).hexdigest() for data in [self.png, other]])
        self.assertTrue(all(not Path(path).exists() for path in paths))
        self.assertEqual(request, original)

    def test_health_declares_two_image_limit(self):
        self.assertEqual(self.client.health(allow_mock=True)['max_images'], 2)

    def test_third_image_is_rejected(self):
        request, _ = self.two_images()
        request['images'].append(copy.deepcopy(request['images'][0]))
        with self.assertRaises(ProtocolError):
            validate_request(request)

    def test_second_invalid_image_never_reaches_engine(self):
        request, _ = self.two_images()
        request['images'][1]['data'] = '%%'
        from visual_lab.client import ModelAPIError
        with self.assertRaises(ModelAPIError):
            self.client.predict(request)
        self.assertEqual(self.bridge.requests_completed, 0)

    def test_two_temp_files_are_cleaned_after_engine_failure(self):
        request, _ = self.two_images()
        paths = []
        def predict(internal):
            paths.extend(internal['images'])
            raise RuntimeError('synthetic two-image failure')
        self.bridge.engine = type('E', (), {'metadata': {'is_mock': True}, 'predict': staticmethod(predict)})()
        from visual_lab.client import ModelAPIError
        with self.assertRaises(ModelAPIError):
            self.client.predict(request)
        self.assertEqual(len(paths), 2)
        self.assertTrue(all(not Path(path).exists() for path in paths))


class ProcessorAuditTests(unittest.TestCase):
    def test_truncating_processor_call_is_rejected_before_processing(self):
        from visual_lab.server import ProcessorAudit
        from unittest.mock import Mock
        from PIL import Image
        grid = type('Grid', (), {'tolist': lambda s: [[1, 2, 2], [1, 2, 2]]})()
        ids = type('Ids', (), {'shape': (1, 8192)})()
        processor = Mock(return_value={'image_grid_thw': grid, 'input_ids': ids})
        proxy = ProcessorAudit(processor)
        with self.assertRaisesRegex(ProtocolError, 'truncation'):
            proxy(images=[Image.new('RGB', (2, 2))]*2, text=['long input'], truncation=True)
        processor.assert_not_called()

    def test_records_actual_rgb_order_and_grid_without_changing_batch(self):
        from visual_lab.server import ProcessorAudit
        from PIL import Image
        images = [Image.new('RGB', (2, 2), color) for color in ['red', 'green']]
        grid = type('Grid', (), {'tolist': lambda s: [[1, 2, 2], [1, 2, 2]]})()
        ids = type('Ids', (), {'shape': (1, 60)})()
        batch = {'image_grid_thw': grid, 'input_ids': ids}
        processor = type('P', (), {'tag': 'processor', '__call__': lambda s, **kw: batch})()
        proxy = ProcessorAudit(processor)
        self.assertIs(proxy(images=images, text=['x']), batch)
        self.assertEqual(proxy.tag, 'processor')
        self.assertEqual(proxy.last['normalized_rgb_sha256s'], [hashlib.sha256(image.tobytes()).hexdigest() for image in images])
        self.assertEqual(proxy.last['image_grid_thw'], [[1, 2, 2], [1, 2, 2]])


if __name__ == '__main__':
    unittest.main()
