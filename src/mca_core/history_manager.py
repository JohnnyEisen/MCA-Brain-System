"""History Manager Module - SECURE VERSION

Centralized history file management with rotation, backup, and integrity protection.
Fix V-005: CSV formula injection vulnerability
"""
from __future__ import annotations
import os
import csv
import json
import shutil
import logging
from datetime import datetime
from typing import Optional
from config.constants import HISTORY_FILE, HISTORY_DIR

logger = logging.getLogger(__name__)

# History rotation threshold: 5MB
HISTORY_SIZE_LIMIT = 5 * 1024 * 1024


# ============================================================
# V-005 Fix: CSV injection protection
# ============================================================

def _sanitize_csv_value(value: str, max_length: int = 800) -> str:
    """
    Sanitize CSV value to prevent formula injection.
    
    Attack: Excel interprets cells starting with =, +, -, @ as formulas
    Protection: Add single quote prefix (display as text)
    """
    if not value:
        return ""
    
    # Truncate length
    value = value[:max_length]
    
    # If starts with dangerous char, add escape prefix
    dangerous_prefixes = ('=', '+', '-', '@', '\t', '\r', '\n')
    if value.startswith(dangerous_prefixes):
        value = "'" + value  # Single quote forces Excel to display as text
    
    # Remove control characters
    value = ''.join(char for char in value if ord(char) >= 32 or char in '\n\r')
    
    return value


def should_rotate_history() -> bool:
    """Check if history file should be rotated."""
    if not os.path.exists(HISTORY_FILE):
        return False
    return os.path.getsize(HISTORY_FILE) > HISTORY_SIZE_LIMIT


def rotate_history() -> bool:
    """
    Rotate history file: compress old data to zip and clear.
    
    Returns:
        True if rotation was performed, False otherwise
    """
    if not should_rotate_history():
        return False
    
    try:
        import zipfile
        import time
        
        archive_path = os.path.join(HISTORY_DIR, "history_archive.zip")
        
        # Compress to zip
        with zipfile.ZipFile(archive_path, "a", zipfile.ZIP_DEFLATED) as zf:
            zf.write(HISTORY_FILE, arcname=f"history_{int(time.time())}.csv")
        
        # Safe clear: backup first, then clear
        backup_path = HISTORY_FILE + ".tmp"
        shutil.move(HISTORY_FILE, backup_path)
        with open(HISTORY_FILE, "w", encoding="utf-8-sig", newline="") as f:
            pass
        os.remove(backup_path)
        
        logger.info(f"History rotated: {archive_path}")
        return True
        
    except Exception as e:
        logger.warning(f"History rotation failed: {e}")
        return False


def append_history(summary: str, file_path: str) -> bool:
    """
    Append a new entry to history file.
    
    Args:
        summary: Analysis summary text
        file_path: Path to the analyzed file
        
    Returns:
        True if successful, False otherwise
    """
    try:
        # Check and rotate if needed
        rotate_history()
        
        with open(HISTORY_FILE, "a", encoding="utf-8-sig", newline="") as f:
            writer = csv.writer(f)
            current_time = datetime.now().isoformat()
            # V-005 Fix: Use sanitization function
            safe_summary = _sanitize_csv_value(summary[:800])
            safe_path = _sanitize_csv_value(file_path)
            writer.writerow([current_time, safe_summary, safe_path])
        
        return True
        
    except Exception as e:
        logger.warning(f"Failed to append history: {e}")
        return False


def read_history(limit: int = 100) -> list:
    """
    Read history entries.
    
    Args:
        limit: Maximum number of entries to read
        
    Returns:
        List of (timestamp, summary, file_path) tuples
    """
    if not os.path.exists(HISTORY_FILE):
        return []
    
    try:
        with open(HISTORY_FILE, "r", encoding="utf-8-sig") as f:
            reader = csv.reader(f)
            rows = list(reader)
            return rows[-limit:] if len(rows) > limit else rows
            
    except Exception as e:
        logger.warning(f"Failed to read history: {e}")
        return []


def clear_history() -> bool:
    """Clear history file."""
    try:
        if os.path.exists(HISTORY_FILE):
            os.remove(HISTORY_FILE)
        return True
    except Exception as e:
        logger.warning(f"Failed to clear history: {e}")
        return False


def get_history_count() -> int:
    """Get number of history entries."""
    if not os.path.exists(HISTORY_FILE):
        return 0
    try:
        with open(HISTORY_FILE, "r", encoding="utf-8-sig") as f:
            return sum(1 for _ in f)
    except:
        return 0
