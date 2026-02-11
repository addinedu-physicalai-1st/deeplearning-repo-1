# -*- coding: utf-8 -*-
"""
InitWindow: 서버 초기화 후 DB 체크 윈도우로 진행.
(Client와 달리 rtsp_test, webcam_test 없음.)
"""

import os
import sys
import time
from PyQt6.QtWidgets import QApplication, QMainWindow, QLabel, QVBoxLayout, QWidget
from PyQt6.QtGui import QFont, QPixmap
from PyQt6.QtCore import Qt, QTimer

_SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
_PROJECT_ROOT = os.path.dirname(_SCRIPT_DIR)
if _PROJECT_ROOT not in sys.path:
    sys.path.insert(0, _PROJECT_ROOT)

from db_check_window import DbCheckWindow
from env_config import ensure_env_file, load_env, read_env_values, update_env_file


class InitWindow(QMainWindow):
    """서버 초기화 후 DB 체크 윈도우를 띄움."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("서버 초기화")
        self.setMinimumSize(420, 380)
        self.resize(520, 480)
        self._center_on_screen()
        self._init_ui()
        self._init_complete = False
        QTimer.singleShot(0, self._run_init_flow)

    def _init_ui(self):
        central = QWidget(self)
        self.setCentralWidget(central)
        layout = QVBoxLayout(central)
        layout.setSpacing(10)
        # 상단 상태 라벨: 다크 모드에서도 잘 보이도록 어두운 배경 + 밝은 글자
        self.status_label = QLabel("설정을 확인하는 중...")
        self.status_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.status_label.setFont(QFont("", 11))
        self.status_label.setStyleSheet(
            "padding: 8px; background-color: #2d2d2d; color: #e8e8e8; border-radius: 4px;"
        )
        self.status_label.setWordWrap(True)
        layout.addWidget(self.status_label)
        # 이미지 영역 (선택: AI_Care 이미지가 있으면 표시, 텍스트도 다크 모드용 색상)
        img_path = os.path.join(_SCRIPT_DIR, "AI_Care_Img1.png")
        if not os.path.isfile(img_path):
            img_path = os.path.join(_PROJECT_ROOT, "AI_Care_Img1.png")
        self.image_label = QLabel()
        self.image_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.image_label.setMinimumHeight(240)
        self.image_label.setStyleSheet(
            "background-color: #252525; color: #b0b0b0; border-radius: 4px;"
        )
        if os.path.isfile(img_path):
            pix = QPixmap(img_path)
            if not pix.isNull():
                scaled = pix.scaled(400, 280, Qt.AspectRatioMode.KeepAspectRatio, Qt.TransformationMode.SmoothTransformation)
                self.image_label.setPixmap(scaled)
            else:
                self.image_label.setText("(이미지를 불러올 수 없습니다)")
        else:
            self.image_label.setText("(이미지 없음)")
        layout.addWidget(self.image_label, 1)

    def _center_on_screen(self):
        screen = self.screen()
        if screen is None:
            return
        screen_geo = screen.availableGeometry()
        frame = self.frameGeometry()
        frame.moveCenter(screen_geo.center())
        self.move(frame.topLeft())

    def _run_init_flow(self):
        app = QApplication.instance()
        ensure_env_file(base_dir=_SCRIPT_DIR)
        load_env(base_dir=_SCRIPT_DIR)
        client_dir = os.path.join(_PROJECT_ROOT, "client")
        ensure_env_file(base_dir=client_dir)
        server_env = read_env_values(base_dir=_SCRIPT_DIR)
        # DB_NAME은 제외: 클라이언트는 자체 DB_NAME(client: home_safe_user 등) 유지, 서버 값으로 덮어쓰지 않음
        sync_keys = {
            k: v for k, v in server_env.items()
            if (k.startswith("DB_") and k != "DB_NAME") or k in ("API_HOST", "API_PORT")
        }
        if sync_keys:
            update_env_file(base_dir=client_dir, updates=sync_keys)
        self.status_label.setText("설정을 확인하는 중...")
        app.processEvents()
        time.sleep(1)
        self.status_label.setText("DB 확인을 진행합니다...")
        app.processEvents()
        time.sleep(1)
        self._init_complete = True
        self._open_db_check_and_close()

    def _open_db_check_and_close(self):
        """DB 체크 윈도우를 띄우고 본 창은 닫음."""
        self.db_check_win = DbCheckWindow(parent=None)
        self.db_check_win.show()
        self.close()

    def closeEvent(self, event):
        if not getattr(self, "_init_complete", False):
            event.accept()
            QApplication.instance().quit()
            return
        super().closeEvent(event)
