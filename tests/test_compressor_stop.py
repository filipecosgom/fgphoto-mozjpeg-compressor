import threading
import unittest
from unittest.mock import Mock
from pathlib import Path

from main import Compressor, find_duplicate_output_paths


class CompressorStopTests(unittest.TestCase):
    """Verify that Stop reaches the active encoder process."""

    def test_stop_terminates_active_process(self):
        worker = Compressor.__new__(Compressor)
        worker._stop_event = threading.Event()
        worker._process_lock = threading.Lock()
        worker._active_process = Mock()
        worker._active_process.poll.return_value = None

        worker.stop()

        self.assertTrue(worker._stop_event.is_set())
        worker._active_process.terminate.assert_called_once_with()

    def test_stop_does_not_terminate_a_finished_process(self):
        worker = Compressor.__new__(Compressor)
        worker._stop_event = threading.Event()
        worker._process_lock = threading.Lock()
        worker._active_process = Mock()
        worker._active_process.poll.return_value = 0

        worker.stop()

        self.assertTrue(worker._stop_event.is_set())
        worker._active_process.terminate.assert_not_called()

    def test_duplicate_output_paths_are_reported(self):
        tasks = [
            (Path("source/photo.jpg"), Path("export/photo_compressed_80.jpg")),
            (Path("source/photo.png"), Path("export/photo_compressed_80.jpg")),
        ]

        duplicates = find_duplicate_output_paths(tasks)

        self.assertEqual(duplicates, [Path("export/photo_compressed_80.jpg")])

    def test_output_path_comparison_is_case_insensitive(self):
        tasks = [
            (Path("source/one.jpg"), Path("export/Photo.jpg")),
            (Path("source/two.jpg"), Path("export/photo.jpg")),
        ]

        duplicates = find_duplicate_output_paths(tasks)

        self.assertEqual(len(duplicates), 1)


if __name__ == "__main__":
    unittest.main()
