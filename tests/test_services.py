import unittest
import sys
import os
import shutil
import tempfile
from unittest.mock import MagicMock, patch

# Ensure root dir is in sys.path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from mca_core.services.config_service import ConfigService
from mca_core.services.system_service import SystemService
from config.app_config import AppConfig

class TestConfigService(unittest.TestCase):
    def setUp(self):
        self.test_dir = tempfile.mkdtemp()
        self.config_path = os.path.join(self.test_dir, "test_config.json")
        self.service = ConfigService(self.config_path)

    def tearDown(self):
        shutil.rmtree(self.test_dir)

    def test_default_values(self):
        # Should use defaults when file doesn't exist
        # DEFAULT_SCROLL_SENSITIVITY is 6 in constants.py (defined twice, last one wins)
        self.assertEqual(self.service.get_scroll_sensitivity(), 6)
        # HIGHLIGHT_SIZE_LIMIT is 300_000 in constants.py
        self.assertEqual(self.service.get_highlight_size_limit(), 300000)

    def test_save_and_load(self):
        self.service.set_scroll_sensitivity(5)
        self.service.set_highlight_size_limit(100)
        self.service.save()

        # Create new service instance to load from file
        new_service = ConfigService(self.config_path)
        self.assertEqual(new_service.get_scroll_sensitivity(), 5)
        self.assertEqual(new_service.get_highlight_size_limit(), 100)

class TestSystemService(unittest.TestCase):
    def setUp(self):
        self.service = SystemService()

    def test_get_system_info_structure(self):
        info = self.service.get_system_info()
        self.assertIn('platform', info)
        self.assertIn('python', info)
        # These might be missing if deps not installed, but keys check is good
        
    @patch('mca_core.services.system_service.platform')
    def test_cached_info(self, mock_platform):
        mock_platform.platform.return_value = "MockOS"
        mock_platform.python_version.return_value = "3.9.9"
        
        info1 = self.service.get_system_info()
        self.assertEqual(info1['platform'], "MockOS")
        
        # Change mock to verify cache is used (should NOT change)
        mock_platform.platform.return_value = "ChangedOS"
        info2 = self.service.get_system_info()
        self.assertEqual(info2['platform'], "MockOS")

if __name__ == '__main__':
    unittest.main()
