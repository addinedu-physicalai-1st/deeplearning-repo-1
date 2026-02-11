import os
import sys

from PyQt6.QtWidgets import (
    QDialog,
    QLabel,
    QPushButton,
    QVBoxLayout,
    QHBoxLayout,
    QFormLayout,
    QLineEdit,
    QComboBox,
    QDateEdit,
    QMessageBox,
)
from PyQt6.QtCore import Qt, QDate

_SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
_PROJECT_ROOT = os.path.dirname(_SCRIPT_DIR)
if _PROJECT_ROOT not in sys.path:
    sys.path.insert(0, _PROJECT_ROOT)

from api_client import register_user
from get_device_id import get_device_id


class RegisterWindow(QDialog):
    """사용자 신규 등록 창."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("신규 등록")
        self.setMinimumSize(420, 360)
        self.resize(520, 480)
        self._init_ui()
        self._center_on_screen()

    def _init_ui(self):
        layout = QVBoxLayout(self)
        title = QLabel("신규 등록")
        title.setAlignment(Qt.AlignmentFlag.AlignCenter)
        title.setStyleSheet("font-weight: bold; font-size: 14px;")
        layout.addWidget(title)

        form = QFormLayout()
        self.ed_user_id = QLineEdit()
        self.ed_password = QLineEdit()
        self.ed_password.setEchoMode(QLineEdit.EchoMode.Password)
        self.ed_name = QLineEdit()
        self.cb_gender = QComboBox()
        self.cb_gender.addItems(["M", "F"])
        self.ed_blood_type = QLineEdit()
        self.ed_address = QLineEdit()
        self.ed_birth_date = QDateEdit()
        self.ed_birth_date.setCalendarPopup(True)
        self.ed_birth_date.setDate(QDate.currentDate())
        self.ed_phone = QLineEdit()
        self.ed_emergency_phone = QLineEdit()
        self.cb_user_type = QComboBox()
        self.cb_user_type.addItems(["NORMAL", "MONITOR"])
        self.ed_monitor_target_id = QLineEdit()

        form.addRow("아이디*", self.ed_user_id)
        form.addRow("비밀번호*", self.ed_password)
        form.addRow("이름*", self.ed_name)
        form.addRow("성별", self.cb_gender)
        form.addRow("혈액형", self.ed_blood_type)
        form.addRow("주소", self.ed_address)
        form.addRow("생년월일", self.ed_birth_date)
        form.addRow("연락처", self.ed_phone)
        form.addRow("비상연락처", self.ed_emergency_phone)
        form.addRow("사용자 유형", self.cb_user_type)
        form.addRow("감시 대상 ID", self.ed_monitor_target_id)
        layout.addLayout(form)

        btn_layout = QHBoxLayout()
        self.btn_register = QPushButton("등록")
        self.btn_close = QPushButton("닫기")
        btn_layout.addWidget(self.btn_register)
        btn_layout.addWidget(self.btn_close)
        layout.addLayout(btn_layout)

        self.btn_register.clicked.connect(self._register)
        self.btn_close.clicked.connect(self.close)

    def _center_on_screen(self):
        screen = self.screen()
        if screen is None:
            return
        screen_geo = screen.availableGeometry()
        frame = self.frameGeometry()
        frame.moveCenter(screen_geo.center())
        self.move(frame.topLeft())

    def _register(self):
        user_id = self.ed_user_id.text().strip()
        password = self.ed_password.text().strip()
        name = self.ed_name.text().strip()
        if not user_id or not password or not name:
            QMessageBox.warning(self, "입력 오류", "아이디/비밀번호/이름은 필수입니다.")
            return

        payload = {
            "user_id": user_id,
            "password": password,
            "name": name,
            "device_id": get_device_id(),
            "gender": self.cb_gender.currentText(),
            "blood_type": self.ed_blood_type.text().strip() or None,
            "address": self.ed_address.text().strip() or None,
            "birth_date": self.ed_birth_date.date().toString("yyyy-MM-dd"),
            "phone": self.ed_phone.text().strip() or None,
            "emergency_phone": self.ed_emergency_phone.text().strip() or None,
            "user_type": self.cb_user_type.currentText(),
            "monitor_target_id": self.ed_monitor_target_id.text().strip() or None,
        }
        ok, msg = register_user(payload)
        if ok:
            QMessageBox.information(self, "등록 완료", "신규 등록이 완료되었습니다.")
            self.accept()
        else:
            # 서버에서 어떤 에러(JSON detail 등)가 오더라도, 사용자에게는 단순 메시지만 노출
            QMessageBox.warning(self, "등록 실패", "등록이 실패하였습니다.")
