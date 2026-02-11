# -*- coding: utf-8 -*-
"""
DbCheckWindow: DB 연결 확인 후 완료 시 관리자 로그인 창을 띄움.
"""

import os
import sys
import time
from PyQt6.QtWidgets import (
    QApplication,
    QMainWindow,
    QMessageBox,
    QLabel,
    QVBoxLayout,
    QWidget,
    QPushButton,
)
from PyQt6.QtGui import QFont
from PyQt6.QtCore import Qt, QTimer

_SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
_PROJECT_ROOT = os.path.dirname(_SCRIPT_DIR)
if _PROJECT_ROOT not in sys.path:
    sys.path.insert(0, _PROJECT_ROOT)

from admin_login_window import AdminLoginWindow
from env_config import get_db_config, test_db_connection


class DbCheckWindow(QMainWindow):
    """DB 연결 확인 윈도우. 확인 완료 시 관리자 로그인 창 오픈."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("DB 연결 확인")
        self.setMinimumSize(400, 200)
        self.resize(480, 260)
        self._center_on_screen()
        self._init_ui()
        self._check_complete = False
        QTimer.singleShot(0, self._run_db_check)

    def _init_ui(self):
        central = QWidget(self)
        self.setCentralWidget(central)
        layout = QVBoxLayout(central)
        layout.setSpacing(12)
        # 상태 라벨: 다크 모드에서 잘 보이도록 어두운 배경 + 밝은 글자
        self.status_label = QLabel("DB 연결을 확인하는 중...")
        self.status_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.status_label.setFont(QFont("", 11))
        self.status_label.setStyleSheet(
            "padding: 8px; background-color: #2d2d2d; color: #e8e8e8; border-radius: 4px;"
        )
        self.status_label.setWordWrap(True)
        layout.addWidget(self.status_label)
        self.btn_retry = QPushButton("다시 확인")
        self.btn_retry.setMinimumHeight(36)
        self.btn_retry.clicked.connect(self._run_db_check)
        self.btn_retry.hide()
        layout.addWidget(self.btn_retry)
        layout.addStretch()

    def _center_on_screen(self):
        screen = self.screen()
        if screen is None:
            return
        screen_geo = screen.availableGeometry()
        frame = self.frameGeometry()
        frame.moveCenter(screen_geo.center())
        self.move(frame.topLeft())

    def _run_db_check(self):
        """DB 연결 확인."""
        app = QApplication.instance()
        self.status_label.setText("DB 연결을 확인하는 중...")
        self.btn_retry.hide()
        app.processEvents()
        time.sleep(1)
        success, error_msg = test_db_connection(get_db_config(base_dir=_SCRIPT_DIR))
        if success:
            self.status_label.setText("DB 연결 확인 완료.")
            app.processEvents()
            time.sleep(0.5)
            self._check_complete = True
            self._open_admin_login_and_close()
            return

        QMessageBox.critical(self, "DB 연결 실패", "환경설정파일을 확인해주세요.")
        QApplication.instance().quit()

    def _open_admin_login_and_close(self):
        """관리자 로그인 창을 띄우고 본 창 닫음."""
        self._login_win = AdminLoginWindow(parent=None)
        self._login_win.show()
        self.close()
