# -*- coding: utf-8 -*-
"""
서버 관리자 로그인 창.

home_safe_admin.admin_users 테이블의 admin_id / admin_pw를 확인하여
일치하면 MainWindow를 띄우고, 일치하지 않으면 경고 후 머무른다.
"""

import os
import sys

from PyQt6.QtWidgets import (
    QDialog,
    QLabel,
    QLineEdit,
    QPushButton,
    QVBoxLayout,
    QHBoxLayout,
    QMessageBox,
)
from PyQt6.QtCore import Qt

_SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
_PROJECT_ROOT = os.path.dirname(_SCRIPT_DIR)
if _PROJECT_ROOT not in sys.path:
    sys.path.insert(0, _PROJECT_ROOT)

from env_config import get_db_config  # type: ignore
from main_window import MainWindow  # type: ignore


class AdminLoginWindow(QDialog):
    """관리자 로그인 창 (서버 전용)."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self._main_win = None
        self.setWindowTitle("서버 관리자 로그인")
        self.setMinimumSize(360, 220)
        self.resize(420, 260)
        self._init_ui()
        self._center_on_screen()

    def _init_ui(self):
        layout = QVBoxLayout(self)

        title = QLabel("서버 관리자 로그인")
        title.setAlignment(Qt.AlignmentFlag.AlignCenter)
        title.setStyleSheet("font-weight: bold; font-size: 14px;")
        layout.addWidget(title)

        self.ed_admin_id = QLineEdit()
        self.ed_admin_id.setPlaceholderText("관리자 ID")
        self.ed_admin_pw = QLineEdit()
        self.ed_admin_pw.setPlaceholderText("관리자 비밀번호")
        self.ed_admin_pw.setEchoMode(QLineEdit.EchoMode.Password)
        layout.addWidget(self.ed_admin_id)
        layout.addWidget(self.ed_admin_pw)

        btn_layout = QHBoxLayout()
        self.btn_login = QPushButton("로그인")
        self.btn_close = QPushButton("닫기")
        btn_layout.addWidget(self.btn_login)
        btn_layout.addWidget(self.btn_close)
        layout.addLayout(btn_layout)

        self.btn_login.clicked.connect(self._login)
        self.btn_close.clicked.connect(self.close)

    def _center_on_screen(self):
        screen = self.screen()
        if screen is None:
            return
        geo = screen.availableGeometry()
        frame = self.frameGeometry()
        frame.moveCenter(geo.center())
        self.move(frame.topLeft())

    def _login(self):
        admin_id = self.ed_admin_id.text().strip()
        admin_pw = self.ed_admin_pw.text().strip()

        if not admin_id or not admin_pw:
            QMessageBox.warning(self, "입력 오류", "관리자 ID와 비밀번호를 입력해주세요.")
            return

        ok, msg = self._check_admin_credentials(admin_id, admin_pw)
        if not ok:
            QMessageBox.warning(self, "로그인 실패", msg)
            return

        QMessageBox.information(self, "로그인 성공", "관리자 로그인에 성공했습니다.")
        if self._main_win is None or not self._main_win.isVisible():
            self._main_win = MainWindow(parent=None)
        self._main_win.show()
        self._main_win.raise_()
        self._main_win.activateWindow()
        self.close()

    def _check_admin_credentials(self, admin_id: str, admin_pw: str) -> tuple[bool, str]:
        """
        home_safe_admin.admin_users 테이블에서 관리자 인증.

        현재는 개발용으로 평문 비교 (admin_pw 컬럼).
        """
        try:
            import pymysql  # type: ignore
        except Exception as exc:  # pragma: no cover - 환경 의존
            return False, f"DB 드라이버(pymysql) 로드 실패: {exc}"

        cfg = get_db_config(base_dir=_SCRIPT_DIR)
        try:
            conn = pymysql.connect(
                host=cfg["host"],
                port=cfg["port"],
                user=cfg["user"],
                password=cfg["password"],
                database=cfg["name"],
                charset="utf8mb4",
            )
        except Exception as exc:
            return False, f"DB 연결 실패: {exc}"

        try:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    SELECT admin_pw, admin_role, is_active
                    FROM admin_users
                    WHERE admin_id = %s
                    """,
                    (admin_id,),
                )
                row = cur.fetchone()
        finally:
            conn.close()

        if not row:
            return False, "관리자 ID 또는 비밀번호가 올바르지 않습니다."

        db_pw, admin_role, is_active = row
        if not is_active:
            return False, "비활성화된 관리자 계정입니다."

        # 개발용: 평문 비교
        if str(db_pw) != admin_pw:
            return False, "관리자 ID 또는 비밀번호가 올바르지 않습니다."

        # TODO: admin_role에 따라 추가 권한 제어가 필요하면 여기서 처리
        return True, "ok"

