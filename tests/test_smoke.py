import unittest
import os
import sys

# Ensure root dir is in path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

class TestSmoke(unittest.TestCase):
    def test_imports(self):
        """Verify that critical modules can be imported without error."""
        try:
            import mca_core.app
            import mca_core.learning
            import mca_core.file_io
            import config.constants
            import tools.generate_mc_log
        except ImportError as e:
            self.fail(f"Import failed: {e}")

    def test_constants_values(self):
        """Verify that constants are correctly loaded."""
        from config.constants import AI_SEMANTIC_LIMIT, LAB_HEAD_READ_SIZE
        self.assertEqual(AI_SEMANTIC_LIMIT, 4096)
        self.assertEqual(LAB_HEAD_READ_SIZE, 128 * 1024)

    def test_learning_initialization(self):
        """Verify that CrashPatternLearner initializes correctly."""
        from mca_core.learning import CrashPatternLearner
        learner = CrashPatternLearner(os.path.join(os.path.dirname(__file__), "dummy_data"))
        self.assertIsNotNone(learner)

if __name__ == "__main__":
    unittest.main()
