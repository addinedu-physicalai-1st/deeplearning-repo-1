import os
import sys

from PyQt6.QtWidgets import (
    QDialog,
    QLabel,
    QPushButton,
    QVBoxLayout,
    QHBoxLayout,
    QLineEdit,
    QMessageBox,
)
from PyQt6.QtCore import Qt

_SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
_PROJECT_ROOT = os.path.dirname(_SCRIPT_DIR)
if _PROJECT_ROOT not in sys.path:
    sys.path.insert(0, _PROJECT_ROOT)

from api_client import login_user, login_admin
from register_window import RegisterWindow
from main_window import MainWindow
from env_config import update_env_file, read_env_values


class LoginWindow(QDialog):
    """로그인 창."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("로그인")
        self.setMinimumSize(360, 220)
        self.resize(420, 260)
        self._main_win = None
        self._init_ui()
        self._center_on_screen()
        # 현재 MODE에 따라 신규등록 버튼 표시 여부 결정
        env = read_env_values(base_dir=_SCRIPT_DIR)
        current_mode = (env.get("MODE") or "user").strip().lower()
        # 관리자 모드일 때는 신규등록 버튼 숨김, 사용자 모드일 때는 표시
        self.btn_register.setVisible(current_mode != "admin")

    def _init_ui(self):
        layout = QVBoxLayout(self)
        title = QLabel("로그인")
        title.setAlignment(Qt.AlignmentFlag.AlignCenter)
        title.setStyleSheet("font-weight: bold; font-size: 14px;")
        layout.addWidget(title)

        self.ed_user_id = QLineEdit()
        self.ed_user_id.setPlaceholderText("아이디")
        self.ed_password = QLineEdit()
        self.ed_password.setPlaceholderText("비밀번호")
        self.ed_password.setEchoMode(QLineEdit.EchoMode.Password)
        layout.addWidget(self.ed_user_id)
        layout.addWidget(self.ed_password)

        btn_layout = QHBoxLayout()
        self.btn_login = QPushButton("로그인")
        self.btn_register = QPushButton("신규등록")
        btn_layout.addWidget(self.btn_login)
        btn_layout.addWidget(self.btn_register)
        layout.addLayout(btn_layout)

        self.btn_close = QPushButton("닫기")
        self.btn_close.clicked.connect(self.close)
        layout.addWidget(self.btn_close, alignment=Qt.AlignmentFlag.AlignRight)

        self.btn_login.clicked.connect(self._login)
        self.btn_register.clicked.connect(self._open_register)

    def _center_on_screen(self):
        screen = self.screen()
        if screen is None:
            return
        screen_geo = screen.availableGeometry()
        frame = self.frameGeometry()
        frame.moveCenter(screen_geo.center())
        self.move(frame.topLeft())

    def _login(self):
        user_id = self.ed_user_id.text().strip()
        password = self.ed_password.text().strip()
        if not user_id or not password:
            QMessageBox.warning(self, "입력 오류", "아이디와 비밀번호를 입력해주세요.")
            return
        # 현재 MODE 확인 (admin 모드인지 여부)
        env = read_env_values(base_dir=_SCRIPT_DIR)
        current_mode = (env.get("MODE") or "user").strip().lower()

        # 1) .env MODE=admin 이면 관리자 로그인 플로우
        if current_mode == "admin":
            ok, msg = login_admin(user_id, password)
            if ok:
                # 관리자 로그인 성공 유지
                update_env_file(base_dir=_SCRIPT_DIR, updates={"MODE": "admin"})
                QMessageBox.information(self, "관리자 로그인", "관리자 로그인에 성공했습니다.")
                if self._main_win is None or not self._main_win.isVisible():
                    self._main_win = MainWindow(parent=None, user_id=user_id)
                self._main_win.show()
                self._main_win.raise_()
                self._main_win.activateWindow()
                self.close()
            else:
                # 관리자 로그인 실패: 알림 후 MODE를 user로 되돌리고 프로그램 종료
                QMessageBox.warning(self, "관리자 로그인 실패", msg)
                update_env_file(base_dir=_SCRIPT_DIR, updates={"MODE": "user"})
                # 프로그램 전체 종료
                from PyQt6.QtWidgets import QApplication
                QApplication.instance().quit()
            return

        # 2) MODE=user: 일반 사용자 로그인 → /auth/login (users 테이블)
        ok, msg = login_user(user_id, password)
        if ok:
            update_env_file(base_dir=_SCRIPT_DIR, updates={"MODE": "user"})
            QMessageBox.information(self, "로그인 성공", "로그인에 성공했습니다.")
            if self._main_win is None or not self._main_win.isVisible():
                self._main_win = MainWindow(parent=None, user_id=user_id)
            self._main_win.show()
            self._main_win.raise_()
            self._main_win.activateWindow()
            self.close()
        else:
            QMessageBox.warning(self, "로그인 실패", msg)

    def _open_register(self):
        dialog = RegisterWindow(self)
        dialog.exec()
