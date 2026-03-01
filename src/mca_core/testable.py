from __future__ import annotations


class DefaultDetectorFactory:
    def create(self):
        return []


class DefaultFileReader:
    def read(self, path: str) -> str:
        with open(path, "r", encoding="utf-8", errors="ignore") as f:
            return f.read()


class DefaultUIUpdater:
    def update(self, data):
        return


class TestableCrashAnalyzer:
    def __init__(self, detector_factory=None, file_reader=None, ui_updater=None):
        self.detector_factory = detector_factory or DefaultDetectorFactory()
        self.file_reader = file_reader or DefaultFileReader()
        self.ui_updater = ui_updater or DefaultUIUpdater()
