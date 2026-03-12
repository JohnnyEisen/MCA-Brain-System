import sys
import os
import unittest
from unittest.mock import MagicMock, patch
import tkinter as tk

# Add root to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# Mock Tkinter components globally before importing app
mock_tk = MagicMock()
sys.modules['tkinter'] = mock_tk
mock_tk.Tk = MagicMock()
mock_tk.StringVar = MagicMock()
mock_tk.IntVar = MagicMock()
mock_tk.BooleanVar = MagicMock()

sys.modules['tkinter.ttk'] = MagicMock()
sys.modules['tkinter.filedialog'] = MagicMock()
sys.modules['tkinter.messagebox'] = MagicMock()
sys.modules['tkinter.scrolledtext'] = MagicMock()

# Mock optional deps
sys.modules['networkx'] = MagicMock()
sys.modules['matplotlib'] = MagicMock()
sys.modules['matplotlib.pyplot'] = MagicMock()
sys.modules['matplotlib.backends.backend_tkagg'] = MagicMock()
sys.modules['tkinterweb'] = MagicMock()

# Import app after mocking
import mca_core.app

class TestAppStartup(unittest.TestCase):
    @patch('mca_core.app.DatabaseManager')
    def test_app_instantiation(self, mock_db_manager):
        # Setup mock for get_instance
        mock_instance = MagicMock()
        mock_db_manager.get_instance.return_value = mock_instance
        
        from mca_core.app import MinecraftCrashAnalyzer
        
        # Mock root
        root = MagicMock()
        
        # Instantiate
        try:
            app = MinecraftCrashAnalyzer(root)
            print("MinecraftCrashAnalyzer instantiated successfully.")
            
            # Verify DB manager was initialized
            self.assertTrue(hasattr(app, 'database_manager'))
            # Check if get_instance was called
            mock_db_manager.get_instance.assert_called()
            
        except Exception as e:
            self.fail(f"Instantiation failed: {e}")

if __name__ == "__main__":
    unittest.main()
