from __future__ import annotations
from typing import Dict
from .errors import AppError


class UnsupportedFormatError(AppError):
    pass


class AnalysisReport:
    def __init__(self, title: str, content: str):
        self.title = title
        self.content = content


class BaseExporter:
    def export(self, report: AnalysisReport, output_path: str) -> None:
        raise NotImplementedError


class HTMLExporter(BaseExporter):
    def export(self, report: AnalysisReport, output_path: str) -> None:
        html = f"<html><head><meta charset='utf-8'><title>{report.title}</title></head><body><pre>{report.content}</pre></body></html>"
        with open(output_path, "w", encoding="utf-8") as f:
            f.write(html)


class MarkdownExporter(BaseExporter):
    def export(self, report: AnalysisReport, output_path: str) -> None:
        with open(output_path, "w", encoding="utf-8") as f:
            f.write(f"# {report.title}\n\n{report.content}\n")


class JSONExporter(BaseExporter):
    def export(self, report: AnalysisReport, output_path: str) -> None:
        import json
        with open(output_path, "w", encoding="utf-8") as f:
            json.dump({"title": report.title, "content": report.content}, f, ensure_ascii=False, indent=2)


class PDFExporter(BaseExporter):
    """Minimal PDF writer (single page, text only)."""
    def export(self, report: AnalysisReport, output_path: str) -> None:
        text = report.content.replace("\\", "\\\\").replace("(", "\\(").replace(")", "\\)")
        lines = text.splitlines()
        content_stream = "BT /F1 12 Tf 50 780 Td "
        for i, line in enumerate(lines[:50]):
            if i > 0:
                content_stream += "0 -14 Td "
            content_stream += f"({line}) Tj "
        content_stream += "ET"
        objects = []
        objects.append("1 0 obj << /Type /Catalog /Pages 2 0 R >> endobj")
        objects.append("2 0 obj << /Type /Pages /Kids [3 0 R] /Count 1 >> endobj")
        objects.append("3 0 obj << /Type /Page /Parent 2 0 R /MediaBox [0 0 595 842] /Contents 4 0 R /Resources << /Font << /F1 5 0 R >> >> >> endobj")
        objects.append(f"4 0 obj << /Length {len(content_stream)} >> stream\n{content_stream}\nendstream endobj")
        objects.append("5 0 obj << /Type /Font /Subtype /Type1 /BaseFont /Helvetica >> endobj")
        xref = ["0000000000 65535 f "]
        offset = 9
        body = "%PDF-1.4\n"
        for obj in objects:
            xref.append(f"{offset:010d} 00000 n ")
            body += obj + "\n"
            offset = len(body.encode("utf-8"))
        xref_offset = offset
        xref_table = "xref\n0 6\n" + "\n".join(xref) + "\n"
        trailer = "trailer << /Size 6 /Root 1 0 R >>\nstartxref\n" + str(xref_offset) + "\n%%EOF"
        with open(output_path, "wb") as f:
            f.write(body.encode("utf-8"))
            f.write(xref_table.encode("utf-8"))
            f.write(trailer.encode("utf-8"))


class ReportExporter:
    def __init__(self):
        self._exporters: Dict[str, BaseExporter] = {
            "html": HTMLExporter(),
            "pdf": PDFExporter(),
            "markdown": MarkdownExporter(),
            "json": JSONExporter(),
        }

    def export(self, report: AnalysisReport, format_type: str, output_path: str):
        exporter = self._exporters.get(format_type)
        if not exporter:
            raise UnsupportedFormatError(format_type)
        exporter.export(report, output_path)
