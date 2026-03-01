from abc import ABC, abstractmethod
from typing import List, Dict, Any, Optional
import json
import os
import logging

logger = logging.getLogger(__name__)

class PatternRepository(ABC):
    """
    Abstract Base Class for Pattern Storage.
    Any future database implementation (TinyDB, SQLite, MongoDB) must inherit from this
    and implement these methods.
    """
    
    @abstractmethod
    def load_all_patterns(self) -> List[Dict[str, Any]]:
        """Load all patterns from the storage."""
        pass

    @abstractmethod
    def get_pattern_by_id(self, pattern_id: str) -> Optional[Dict[str, Any]]:
        """Find a specific pattern by its unique ID."""
        pass

    @abstractmethod
    def save_pattern(self, pattern: Dict[str, Any]) -> bool:
        """Save or update a pattern."""
        pass

    @abstractmethod
    def delete_pattern(self, pattern_id: str) -> bool:
        """Delete a pattern by ID."""
        pass


class JsonFilePatternRepository(PatternRepository):
    """
    Default v1.x implementation: Stores data in a flat JSON file.
    """
    def __init__(self, filepath: str):
        self.filepath = filepath
        self._ensure_file_exists()

    def _ensure_file_exists(self):
        if not self.filepath:
            logger.error(" filepath is empty, cannot create file")
            return
        
        # 安全检查：防止 Windows 特殊设备名
        import os
        basename = os.path.basename(self.filepath)
        if basename.lower() in ('nul', 'aux', 'con', 'prn', 'com1', 'lpt1'):
            logger.error(f"Unsafe filename detected: {basename}")
            return
        
        if not os.path.exists(self.filepath):
            try:
                dir_path = os.path.dirname(self.filepath)
                if dir_path:  # 只有在目录路径非空时才创建
                    os.makedirs(dir_path, exist_ok=True)
                with open(self.filepath, 'w', encoding='utf-8') as f:
                    json.dump({"patterns": []}, f, indent=2, ensure_ascii=False)
            except Exception as e:
                logger.error(f"Failed to init rules file: {e}")
        if not os.path.exists(self.filepath):
            try:
                os.makedirs(os.path.dirname(self.filepath), exist_ok=True)
                with open(self.filepath, 'w', encoding='utf-8') as f:
                    json.dump({"patterns": []}, f, indent=2, ensure_ascii=False)
            except Exception as e:
                logger.error(f"Failed to init rules file: {e}")

    def load_all_patterns(self) -> List[Dict[str, Any]]:
        try:
            with open(self.filepath, 'r', encoding='utf-8') as f:
                data = json.load(f)
                return data.get("patterns", [])
        except (json.JSONDecodeError, FileNotFoundError) as e:
            logger.error(f"Failed to load patterns from JSON: {e}")
            return []

    def get_pattern_by_id(self, pattern_id: str) -> Optional[Dict[str, Any]]:
        patterns = self.load_all_patterns()
        for p in patterns:
            if p.get("id") == pattern_id:
                return p
        return None

    def save_pattern(self, pattern: Dict[str, Any]) -> bool:
        """
        Note: This is inefficient for large datasets (Rewrite-whole-file).
        But it's perfect for small config files (<1MB).
        """
        try:
            current_patterns = self.load_all_patterns()
            # Update existing or Append new
            existing_idx = next((i for i, p in enumerate(current_patterns) if p.get("id") == pattern.get("id")), -1)
            
            if existing_idx >= 0:
                current_patterns[existing_idx] = pattern
            else:
                current_patterns.append(pattern)
            
            self._write_file({"patterns": current_patterns})
            return True
        except Exception as e:
            logger.error(f"Failed to save pattern: {e}")
            return False

    def delete_pattern(self, pattern_id: str) -> bool:
        try:
            current_patterns = self.load_all_patterns()
            new_patterns = [p for p in current_patterns if p.get("id") != pattern_id]
            
            if len(new_patterns) == len(current_patterns):
                return False # Nothing deleted
                
            self._write_file({"patterns": new_patterns})
            return True
        except Exception as e:
            logger.error(f"Failed to delete pattern: {e}")
            return False
            
    def _write_file(self, data: Dict[str, Any]):
        with open(self.filepath, 'w', encoding='utf-8') as f:
            json.dump(data, f, indent=2, ensure_ascii=False)

# Factory helper to switch implementations easily in v1.3
def get_repository(repo_type: str, source: str) -> PatternRepository:
    if repo_type == "json":
        return JsonFilePatternRepository(source)
    # elif repo_type == "tinydb":
    #     return TinyDBRepository(source)
    else:
        raise ValueError(f"Unknown repository type: {repo_type}")
