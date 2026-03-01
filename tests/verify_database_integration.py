import sys
import os
import unittest
from unittest.mock import MagicMock, patch
from collections import Counter, defaultdict

# Add root to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# Mock Tkinter
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

import mca_core.app

class TestDatabaseIntegration(unittest.TestCase):
    @patch('mca_core.app.DatabaseManager')
    def test_record_history(self, mock_db_manager):
        # Setup mock instance
        mock_db_instance = MagicMock()
        mock_db_manager.get_instance.return_value = mock_db_instance
        # Mock add_crash_record to return a valid ID
        mock_db_instance.add_crash_record.return_value = 123
        
        from mca_core.app import MinecraftCrashAnalyzer
        
        # Instantiate
        root = MagicMock()
        app = MinecraftCrashAnalyzer(root)
        
        # Setup dummy data
        app.file_path = "C:/test/crash-2026-01-01.txt"
        app.loader_type = "Fabric"
        app.file_checksum = "abcdef123456"
        
        # Setup analysis results for summary
        app.analysis_results = ["Loader: Fabric", "Mod count: 2", "Error: NullPointerException"]
        
        # Setup mods
        app.mods = defaultdict(set)
        app.mods["fabric-api"] = {"0.90.0"}
        app.mods["sodium"] = {"0.5.0"}
        
        # Setup causes
        app.cause_counts = Counter()
        app.cause_counts["crash.type.npe"] = 1
        
        # Mock open/csv because _record_history also writes to CSV
        with patch("builtins.open", MagicMock()) as mock_file:
             with patch("csv.writer", MagicMock()):
                 # Execute
                 app._record_history()
        
        # Verify add_crash_record
        mock_db_instance.add_crash_record.assert_called_once()
        args, kwargs = mock_db_instance.add_crash_record.call_args
        self.assertEqual(kwargs['file_path'], "C:/test/crash-2026-01-01.txt")
        self.assertEqual(kwargs['loader'], "Fabric")
        self.assertEqual(kwargs['mod_count'], 2)
        self.assertEqual(kwargs['file_hash'], "abcdef123456")
        
        # Verify add_crash_causes
        mock_db_instance.add_crash_causes.assert_called_once()
        call_args = mock_db_instance.add_crash_causes.call_args
        self.assertEqual(call_args[0][0], 123) # crash_id
        causes_arg = call_args[0][1]
        self.assertEqual(len(causes_arg), 1)
        self.assertEqual(causes_arg[0]['type'], "crash.type.npe")
        
        # Verify update_mod_index
        mock_db_instance.update_mod_index.assert_called_once()
        call_args = mock_db_instance.update_mod_index.call_args
        mods_arg = call_args[0][0]
        self.assertEqual(len(mods_arg), 2)
        # Check content roughly
        mod_ids = {m['id'] for m in mods_arg}
        self.assertIn("fabric-api", mod_ids)
        self.assertIn("sodium", mod_ids)
        
        print("Database integration verification passed.")

if __name__ == "__main__":
    unittest.main()
