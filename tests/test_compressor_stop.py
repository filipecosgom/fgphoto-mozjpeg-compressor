import threading
import unittest
from unittest.mock import Mock

from main import Compressor


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


if __name__ == "__main__":
    unittest.main()
