"""프로그램 내장 도움말 다이얼로그 (QTextBrowser 기반)."""
import os
import sys

from PySide6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QTextBrowser, QPushButton, QMessageBox,
)
from PySide6.QtCore import Qt
from PySide6.QtGui import QFont


def _help_html_path():
    if getattr(sys, "frozen", False):
        base = getattr(sys, "_MEIPASS", os.path.dirname(sys.executable))
    else:
        base = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    return os.path.join(base, "도움말_simple.html")


class HelpDialog(QDialog):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("도움말")
        self.resize(920, 720)
        self.setMinimumSize(600, 400)

        lay = QVBoxLayout(self)

        self.browser = QTextBrowser(self)
        self.browser.setOpenExternalLinks(True)
        font = QFont("Malgun Gothic", 10)
        self.browser.setFont(font)

        path = _help_html_path()
        if os.path.isfile(path):
            try:
                with open(path, "r", encoding="utf-8") as f:
                    self.browser.setHtml(f.read())
            except Exception as e:
                self.browser.setPlainText(f"도움말 파일을 읽을 수 없습니다.\n{e}")
        else:
            self.browser.setPlainText(f"도움말 파일을 찾을 수 없습니다.\n{path}")

        lay.addWidget(self.browser, 1)

        btn_row = QHBoxLayout()
        btn_row.addStretch()
        btn_close = QPushButton("닫기")
        btn_close.clicked.connect(self.accept)
        btn_row.addWidget(btn_close)
        lay.addLayout(btn_row)
