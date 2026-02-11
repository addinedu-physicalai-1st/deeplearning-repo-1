# -*- coding: utf-8 -*-
"""
InitWindow: config 확인 후 RTSP/웹캠 테스트로 rtsp_enable, webcam_enable, rtsp_url 설정.
둘 다 false면 안내 후 프로그램 종료.
"""

import os
import sys
import time
from PyQt6.QtWidgets import QApplication, QMainWindow, QMessageBox, QLabel, QVBoxLayout, QWidget
from PyQt6.QtGui import QFont, QPixmap
from PyQt6.QtCore import Qt, QTimer

# 프로젝트 루트를 path에 추가 (rtsp_test, webcam_test import용)
_SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
_PROJECT_ROOT = os.path.dirname(_SCRIPT_DIR)
if _PROJECT_ROOT not in sys.path:
    sys.path.insert(0, _PROJECT_ROOT)

import config as client_config
from rtsp_test import RtspTestWindow
from webcam_test import WebcamTestWindow
from env_config import (
    ensure_env_file,
    load_env,
    read_env_values,
    get_db_config,
    test_db_connection,
    database_exists,
    run_setup_sql_file,
)
from login_window import LoginWindow
from main_window import MainWindow
from api_client import health_check


class InitWindow(QMainWindow):
    """설정 확인/테스트 후 다음 단계로 진행하거나 종료."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("영상 장치 설정")
        self.setMinimumSize(420, 380)
        self.resize(520, 480)
        self._login_win = None
        self._main_win = None
        self._init_ui()
        self._init_complete = False  # X 버튼으로 닫을 때 초기화 미완료면 프로그램 종료용
        # InitWindow가 먼저 show된 뒤 흐름 실행 (다이얼로그가 띄워진 상태에서 테스트 창 추가로 띄움)
        QTimer.singleShot(0, self._run_init_flow)

    def _init_ui(self):
        central = QWidget(self)
        self.setCentralWidget(central)
        layout = QVBoxLayout(central)
        layout.setSpacing(10)
        # 상단: 현재 init 상태 라벨 (다크 모드 가독: 어두운 배경 + 밝은 글자)
        self.status_label = QLabel("설정을 확인하는 중...")
        self.status_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.status_label.setFont(QFont("", 11))
        self.status_label.setStyleSheet(
            "padding: 8px; background-color: #2d2d2d; color: #e8e8e8; border-radius: 4px;"
        )
        self.status_label.setWordWrap(True)
        layout.addWidget(self.status_label)
        # 하단: AI Care 이미지 (다크 모드에서 플레이스홀더 텍스트도 보이도록)
        img_path = os.path.join(_SCRIPT_DIR, "AI_Care_Img1.png")
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
            self.image_label.setText(f"(이미지 없음: {img_path})")
        layout.addWidget(self.image_label, 1)

    def _run_init_flow(self):
        """config 로드/생성 → (config 없었거나 둘 다 false면) RTSP/웹캠 테스트 → 둘 다 false면 종료."""
        ensure_env_file(base_dir=_SCRIPT_DIR)
        load_env(base_dir=_SCRIPT_DIR)
        env = read_env_values(base_dir=_SCRIPT_DIR)
        mode = (env.get("MODE") or "user").strip().lower()
        ok, _ = health_check()
        if not ok:
            if mode == "admin":
                self._open_main_and_close()
                return
            QMessageBox.critical(
                self,
                "서버 연결 실패",
                "서버와 통신이 되지 않습니다.\n서버와 연결 후 사용해 주세요.",
            )
            self.close()
            QApplication.instance().quit()
            return

        # 클라이언트 로컬 DB 연결 확인 (client .env → DB_NAME)
        db_config = get_db_config(base_dir=_SCRIPT_DIR)
        db_name = db_config.get("name", "home_safe_user")
        setup_sql = os.path.join(_SCRIPT_DIR, "home_safe_user_setup.sql")

        def _run_setup_if_needed() -> bool:
            """DB 없을 때 setup 실행. 성공 시 True, 실패 시 False."""
            self.status_label.setText(f"DB({db_name}) 초기화 중...")
            QApplication.instance().processEvents()
            ok_setup, msg_setup = run_setup_sql_file(setup_sql, db_config, connect_timeout=30)
            if not ok_setup:
                cmd_hint = f"mysql -u {db_config.get('user','root')} -p < {setup_sql}"
                QMessageBox.critical(
                    self,
                    "DB 초기화 실패",
                    f"DB 설정 스크립트 실행에 실패했습니다.\n\n{msg_setup}\n\n"
                    f"수동 실행 예시:\n{cmd_hint}",
                )
                self.close()
                QApplication.instance().quit()
                return False
            return True

        # 1) DB 존재 여부 확인 → 없으면 setup 자동 실행 (다이얼로그 없이 진행)
        exists, _ = database_exists(db_config, connect_timeout=3)
        if not exists:
            if not _run_setup_if_needed():
                return

        # 2) DB 연결 확인
        ok_db, msg_db = test_db_connection(db_config, connect_timeout=3)
        if not ok_db:
            QMessageBox.critical(
                self,
                "Client LocalDB 연결 실패",
                f"Client Local DB({db_name}) 연결에 실패했습니다.\nDB 설정 및 환경을 확인해 주세요.",
            )
            self.close()
            QApplication.instance().quit()
            return
        config_path = client_config.get_config_path()
        config_existed = os.path.isfile(config_path)
        cfg = client_config.load_config()

        # config 없었거나, 있어도 rtsp/webcam 둘 다 false면 위저드 실행
        both_disabled = not cfg.get("rtsp_enable", False) and not cfg.get("webcam_enable", False)
        need_rtsp_test = not config_existed or both_disabled
        need_webcam_test = not config_existed or both_disabled

        app = QApplication.instance()
        self.status_label.setText("설정을 확인하는 중...")
        app.processEvents()
        time.sleep(1)
        if need_rtsp_test:
            self.status_label.setText("1/2 RTSP 스트림 설정을 진행합니다...")
            app.processEvents()
            time.sleep(1)
            rtsp_win = RtspTestWindow(wizard_mode=True)
            rtsp_win.show()
            rtsp_win.raise_()
            rtsp_win.activateWindow()
            while rtsp_win.isVisible():
                app.processEvents()
            result = getattr(rtsp_win, "wizard_result", None)
            if result is not None:
                rtsp_enable, rtsp_url = result
                cfg["rtsp_enable"] = rtsp_enable
                cfg["rtsp_url"] = rtsp_url if rtsp_enable else ""
            else:
                cfg["rtsp_enable"] = False
                cfg["rtsp_url"] = ""
            client_config.save_config(cfg)

        if need_webcam_test and not cfg.get("rtsp_enable", False):
            self.status_label.setText("2/2 웹캠 설정을 진행합니다...")
            app.processEvents()
            time.sleep(1)
            webcam_win = WebcamTestWindow(wizard_mode=True)
            webcam_win.show()
            webcam_win.raise_()
            webcam_win.activateWindow()
            while webcam_win.isVisible():
                app.processEvents()
            result = getattr(webcam_win, "wizard_result", None)
            cfg["webcam_enable"] = result if result is not None else False
            client_config.save_config(cfg)

        # 최종 config 다시 로드 (위에서 저장한 값)
        cfg = client_config.load_config()
        rtsp_enable = cfg.get("rtsp_enable", False)
        webcam_enable = cfg.get("webcam_enable", False)
        if not rtsp_enable:
            cfg["rtsp_url"] = ""
            client_config.save_config(cfg)

        if not rtsp_enable and not webcam_enable:
            QMessageBox.critical(
                self,
                "영상 장치 없음",
                "영상 장치를 찾을 수 없습니다.\n장치를 확인해 주세요.",
            )
            self._init_complete = True
            self._open_login_and_close()
            return

        self.status_label.setText(
            "설정이 완료되었습니다.\n"
            + ("RTSP 사용\n" if rtsp_enable else "")
            + ("웹캠 사용\n" if webcam_enable else "")
        )
        app.processEvents()
        time.sleep(1)
        self._config = cfg
        self._init_complete = True
        self._open_login_and_close()

    def closeEvent(self, event):
        if not getattr(self, "_init_complete", False):
            event.accept()
            QApplication.instance().quit()
            return
        super().closeEvent(event)

    def get_config(self):
        """저장된 config dict 반환."""
        return getattr(self, "_config", client_config.load_config())

    def _open_login_and_close(self):
        if self._login_win is None or not self._login_win.isVisible():
            self._login_win = LoginWindow(parent=None)
        self._login_win.show()
        self._login_win.raise_()
        self._login_win.activateWindow()
        self.close()

    def _open_main_and_close(self):
        if self._main_win is None or not self._main_win.isVisible():
            self._main_win = MainWindow(parent=None)
        self._main_win.show()
        self._main_win.raise_()
        self._main_win.activateWindow()
        self.close()
