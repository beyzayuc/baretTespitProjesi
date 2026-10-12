import json
import tempfile
import threading
import unittest
from pathlib import Path
from unittest.mock import patch

import cv2
import numpy as np
from app.engine import process, read_image, save_image


class FakeDetector:
    def detect(self, frame, confidence):
        return frame.copy(), [{'class': 'helmet', 'confidence': .9, 'box': [2, 3, 20, 24]}]


class PipelineTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name)
        self.frame = np.zeros((64, 96, 3), np.uint8)
        self.image = self.root / 'Türkçe fotoğraf.jpg'
        save_image(self.image, self.frame)

    def tearDown(self):
        self.temp.cleanup()

    def run_source(self, source, kind, **kwargs):
        return process(source, kind, 'unused', self.root, detector=FakeDetector(), **kwargs)

    def test_unicode_photo_and_csv(self):
        folder = self.run_source(self.image, 'image')
        self.assertEqual(read_image(folder / 'sonuc.jpg').shape, self.frame.shape)
        self.assertIn('helmet', (folder / 'detections.csv').read_text(encoding='utf-8-sig'))
        self.assertEqual(json.loads((folder / 'summary.json').read_text(encoding='utf-8'))['frames'], 1)

    def video(self):
        path = self.root / 'video.mp4'
        writer = cv2.VideoWriter(str(path), cv2.VideoWriter_fourcc(*'mp4v'), 10, (96, 64))
        self.assertTrue(writer.isOpened())
        for _ in range(5):
            writer.write(self.frame)
        writer.release()
        return path

    def test_video_roundtrip(self):
        folder = self.run_source(self.video(), 'video')
        cap = cv2.VideoCapture(str(folder / 'sonuc.mp4'))
        self.assertEqual(int(cap.get(cv2.CAP_PROP_FRAME_COUNT)), 5)
        self.assertTrue(cap.read()[0])
        cap.release()

    def test_stop_closes_playable_video(self):
        stop = threading.Event()
        folder = self.run_source(self.video(), 'video', stop=stop, callback=lambda *args: stop.set())
        data = json.loads((folder / 'summary.json').read_text(encoding='utf-8'))
        self.assertEqual((data['status'], data['frames']), ('stopped', 1))
        cap = cv2.VideoCapture(str(folder / 'sonuc.mp4'))
        self.assertTrue(cap.read()[0])
        cap.release()

    def test_bad_image(self):
        path = self.root / 'broken.jpg'
        path.write_text('not an image')
        with self.assertRaises(ValueError):
            self.run_source(path, 'image')

    def test_invalid_confidence(self):
        with self.assertRaises(ValueError):
            self.run_source(self.image, 'image', confidence=2)

    def test_camera_disconnect_releases_capture(self):
        with patch('app.engine.cv2.VideoCapture') as factory:
            cap = factory.return_value
            cap.isOpened.return_value = True
            cap.get.return_value = 25
            cap.read.side_effect = [(True, self.frame), (False, None)]
            with self.assertRaises(RuntimeError):
                self.run_source(0, 'camera')
            cap.release.assert_called_once()

    def test_unavailable_camera(self):
        with patch('app.engine.cv2.VideoCapture') as factory:
            factory.return_value.isOpened.return_value = False
            with self.assertRaises(RuntimeError):
                self.run_source(99, 'camera')
            factory.return_value.release.assert_called_once()

    def test_bad_writer(self):
        video = self.video()
        with patch('app.engine.cv2.VideoWriter') as factory:
            factory.return_value.isOpened.return_value = False
            with self.assertRaises(RuntimeError):
                self.run_source(video, 'video')
            factory.return_value.release.assert_called_once()

    def test_opencv_q_releases_and_signals_quit(self):
        from unittest.mock import Mock
        quit_callback=Mock()
        with patch('app.engine.cv2.imshow'), patch('app.engine.cv2.waitKey',return_value=ord('q')), patch('app.engine.cv2.destroyWindow') as close:
            folder=self.run_source(self.video(),'video',show_opencv=True,on_quit=quit_callback)
            quit_callback.assert_called_once()
            close.assert_called_once()
        self.assertEqual(json.loads((folder/'summary.json').read_text(encoding='utf-8'))['status'],'stopped')

if __name__ == '__main__':
    unittest.main()
