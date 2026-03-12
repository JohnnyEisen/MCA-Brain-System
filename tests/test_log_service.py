import unittest
import sys
import os

# Ensure root dir is in sys.path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from mca_core.services.log_service import LogService

class TestLogService(unittest.TestCase):
    def setUp(self):
        self.service = LogService()
        self.sample_log = "Line 1\nLine 2\nError: NullPointerException"

    def test_set_and_get_text(self):
        self.service.set_log_text(self.sample_log)
        self.assertEqual(self.service.get_text(), self.sample_log)

    def test_get_lower(self):
        self.service.set_log_text(self.sample_log)
        expected = self.sample_log.lower()
        self.assertEqual(self.service.get_lower(), expected)
        # Verify caching (access again)
        self.assertEqual(self.service.get_lower(), expected)

    def test_get_lines(self):
        self.service.set_log_text(self.sample_log)
        lines = self.service.get_lines()
        self.assertEqual(len(lines), 3)
        self.assertEqual(lines[2], "Error: NullPointerException")

    def test_get_lines_lower(self):
        self.service.set_log_text(self.sample_log)
        lines = self.service.get_lines(lower=True)
        self.assertEqual(lines[2], "error: nullpointerexception")

    def test_cache_invalidation(self):
        self.service.set_log_text("Old")
        self.assertEqual(self.service.get_lower(), "old")
        
        self.service.set_log_text("New")
        self.assertEqual(self.service.get_lower(), "new")
        self.assertEqual(self.service.get_lines()[0], "New")

if __name__ == '__main__':
    unittest.main()
