import os
import sys
import time
import hashlib

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
    QTableWidget,
    QTableWidgetItem,
    QAbstractItemView,
)
from PyQt6.QtCore import Qt, QDate, pyqtSignal

from db_client import MySqlClient

_SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
_PROJECT_ROOT = os.path.dirname(_SCRIPT_DIR)
if _PROJECT_ROOT not in sys.path:
    sys.path.insert(0, _PROJECT_ROOT)


class UserManageWindow(QDialog):
    """사용자 추가/삭제/수정용 창."""

    list_updated = pyqtSignal()

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("사용자 관리")
        self.setMinimumSize(860, 520)
        self.resize(980, 620)
        self._db = MySqlClient(base_dir=_SCRIPT_DIR)
        self._init_ui()
        self._center_on_screen()
        self._load_users()

    def _init_ui(self):
        layout = QVBoxLayout(self)
        title = QLabel("사용자 관리")
        title.setAlignment(Qt.AlignmentFlag.AlignCenter)
        title.setStyleSheet("font-weight: bold; font-size: 14px;")
        layout.addWidget(title)

        form = QFormLayout()
        self.ed_index_no = QLineEdit()
        self.ed_index_no.setReadOnly(True)
        self.ed_device_id = QLineEdit()
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

        form.addRow("index_no", self.ed_index_no)
        form.addRow("device_id*", self.ed_device_id)
        form.addRow("user_id*", self.ed_user_id)
        form.addRow("password*", self.ed_password)
        form.addRow("name*", self.ed_name)
        form.addRow("gender", self.cb_gender)
        form.addRow("blood_type", self.ed_blood_type)
        form.addRow("address", self.ed_address)
        form.addRow("birth_date", self.ed_birth_date)
        form.addRow("phone", self.ed_phone)
        form.addRow("emergency_phone", self.ed_emergency_phone)
        form.addRow("user_type", self.cb_user_type)
        form.addRow("monitor_target_id", self.ed_monitor_target_id)
        layout.addLayout(form)

        btn_layout = QHBoxLayout()
        self.btn_add = QPushButton("사용자 추가")
        self.btn_edit = QPushButton("사용자 수정")
        self.btn_delete = QPushButton("사용자 삭제")
        self.btn_refresh = QPushButton("새로고침")
        self.btn_clear = QPushButton("입력 초기화")
        btn_layout.addWidget(self.btn_add)
        btn_layout.addWidget(self.btn_edit)
        btn_layout.addWidget(self.btn_delete)
        btn_layout.addWidget(self.btn_refresh)
        btn_layout.addWidget(self.btn_clear)
        layout.addLayout(btn_layout)

        self.table = QTableWidget(0, 10)
        self.table.setHorizontalHeaderLabels(
            [
                "index_no",
                "device_id",
                "user_id",
                "name",
                "gender",
                "blood_type",
                "birth_date",
                "phone",
                "user_type",
                "monitor_target_id",
            ]
        )
        self.table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self.table.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        self.table.itemSelectionChanged.connect(self._on_select_row)
        layout.addWidget(self.table, 1)

        self.btn_close = QPushButton("닫기")
        self.btn_close.clicked.connect(self.close)
        layout.addWidget(self.btn_close, alignment=Qt.AlignmentFlag.AlignRight)

        self.btn_add.clicked.connect(self._add_user)
        self.btn_edit.clicked.connect(self._update_user)
        self.btn_delete.clicked.connect(self._delete_user)
        self.btn_refresh.clicked.connect(self._load_users)
        self.btn_clear.clicked.connect(self._clear_form)

    def _center_on_screen(self):
        screen = self.screen()
        if screen is None:
            return
        screen_geo = screen.availableGeometry()
        frame = self.frameGeometry()
        frame.moveCenter(screen_geo.center())
        self.move(frame.topLeft())

    def _required_ok(self) -> bool:
        if not self.ed_device_id.text().strip():
            QMessageBox.warning(self, "입력 오류", "device_id는 필수입니다.")
            return False
        if not self.ed_user_id.text().strip():
            QMessageBox.warning(self, "입력 오류", "user_id는 필수입니다.")
            return False
        if not self.ed_password.text().strip():
            QMessageBox.warning(self, "입력 오류", "password는 필수입니다.")
            return False
        if not self.ed_name.text().strip():
            QMessageBox.warning(self, "입력 오류", "name은 필수입니다.")
            return False
        return True

    def _load_users(self):
        try:
            rows = self._db.fetch_all(
                "SELECT index_no, device_id, user_id, name, gender, blood_type, birth_date, phone, user_type, monitor_target_id "
                "FROM users ORDER BY created_at DESC"
            )
        except Exception as exc:
            QMessageBox.critical(self, "DB 오류", f"사용자 목록을 불러오지 못했습니다.\n{exc}")
            return
        self.table.setRowCount(0)
        for row in rows:
            r = self.table.rowCount()
            self.table.insertRow(r)
            for c, key in enumerate(
                [
                    "index_no",
                    "device_id",
                    "user_id",
                    "name",
                    "gender",
                    "blood_type",
                    "birth_date",
                    "phone",
                    "user_type",
                    "monitor_target_id",
                ]
            ):
                value = "" if row.get(key) is None else str(row.get(key))
                self.table.setItem(r, c, QTableWidgetItem(value))

    def _on_select_row(self):
        row = self.table.currentRow()
        if row < 0:
            return
        self.ed_index_no.setText(self.table.item(row, 0).text())
        self.ed_device_id.setText(self.table.item(row, 1).text())
        self.ed_user_id.setText(self.table.item(row, 2).text())
        self.ed_name.setText(self.table.item(row, 3).text())
        self.cb_gender.setCurrentText(self.table.item(row, 4).text() or "M")
        self.ed_blood_type.setText(self.table.item(row, 5).text())
        birth = self.table.item(row, 6).text()
        if birth:
            self.ed_birth_date.setDate(QDate.fromString(birth, "yyyy-MM-dd"))
        self.ed_phone.setText(self.table.item(row, 7).text())
        self.cb_user_type.setCurrentText(self.table.item(row, 8).text() or "NORMAL")
        self.ed_monitor_target_id.setText(self.table.item(row, 9).text())

    def _add_user(self):
        if not self._required_ok():
            return
        user_id = self.ed_user_id.text().strip()
        try:
            exists = self._db.fetch_one("SELECT user_id FROM users WHERE user_id=%s", (user_id,))
        except Exception as exc:
            QMessageBox.critical(self, "DB 오류", f"중복 확인에 실패했습니다.\n{exc}")
            return
        if exists:
            QMessageBox.warning(self, "중복 사용자", "이미 존재하는 user_id입니다.")
            return
        try:
            self._db.execute(
                "INSERT INTO users (device_id, user_id, password, name, gender, blood_type, address, birth_date, "
                "phone, emergency_phone, user_type, monitor_target_id) "
                "VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)",
                (
                    self.ed_device_id.text().strip(),
                    self.ed_user_id.text().strip(),
                    self.ed_password.text().strip(),
                    self.ed_name.text().strip(),
                    self.cb_gender.currentText(),
                    self.ed_blood_type.text().strip() or None,
                    self.ed_address.text().strip() or None,
                    self.ed_birth_date.date().toString("yyyy-MM-dd"),
                    self.ed_phone.text().strip() or None,
                    self.ed_emergency_phone.text().strip() or None,
                    self.cb_user_type.currentText(),
                    self.ed_monitor_target_id.text().strip() or None,
                ),
            )
        except Exception as exc:
            # 내부 로그로는 예외를 찍되, 사용자에게는 일반적인 메시지만 보여준다.
            print(f"[UserManageWindow] 사용자 추가 실패: {exc}")
            QMessageBox.critical(self, "등록 실패", "등록이 실패하였습니다.")
            return
        self._load_users()
        self._clear_form()

    def _update_user(self):
        index_no = self.ed_index_no.text().strip()
        if not index_no:
            QMessageBox.warning(self, "선택 필요", "수정할 사용자를 선택해주세요.")
            return
        if not self.ed_device_id.text().strip() or not self.ed_user_id.text().strip() or not self.ed_name.text().strip():
            QMessageBox.warning(self, "입력 오류", "device_id, user_id, name은 필수입니다.")
            return

        fields = [
            ("device_id", self.ed_device_id.text().strip()),
            ("user_id", self.ed_user_id.text().strip()),
            ("name", self.ed_name.text().strip()),
            ("gender", self.cb_gender.currentText()),
            ("blood_type", self.ed_blood_type.text().strip() or None),
            ("address", self.ed_address.text().strip() or None),
            ("birth_date", self.ed_birth_date.date().toString("yyyy-MM-dd")),
            ("phone", self.ed_phone.text().strip() or None),
            ("emergency_phone", self.ed_emergency_phone.text().strip() or None),
            ("user_type", self.cb_user_type.currentText()),
            ("monitor_target_id", self.ed_monitor_target_id.text().strip() or None),
        ]
        if self.ed_password.text().strip():
            fields.insert(3, ("password", self.ed_password.text().strip()))

        set_clause = ", ".join([f"{k}=%s" for k, _ in fields])
        values = tuple(v for _, v in fields) + (index_no,)
        try:
            self._db.execute(f"UPDATE users SET {set_clause} WHERE index_no=%s", values)
        except Exception as exc:
            QMessageBox.critical(self, "DB 오류", f"사용자 수정에 실패했습니다.\n{exc}")
            return
        self._load_users()

    def _delete_user(self):
        index_no = self.ed_index_no.text().strip()
        if not index_no:
            QMessageBox.warning(self, "선택 필요", "삭제할 사용자를 선택해주세요.")
            return
        if QMessageBox.question(self, "삭제 확인", "선택한 사용자를 삭제할까요?") != QMessageBox.StandardButton.Yes:
            return
        try:
            self._db.execute("DELETE FROM users WHERE index_no=%s", (index_no,))
        except Exception as exc:
            QMessageBox.critical(self, "DB 오류", f"사용자 삭제에 실패했습니다.\n{exc}")
            return
        self._load_users()
        self._clear_form()
        self.list_updated.emit()

    def _clear_form(self):
        self.ed_index_no.clear()
        self.ed_device_id.clear()
        self.ed_user_id.clear()
        self.ed_password.clear()
        self.ed_name.clear()
        self.cb_gender.setCurrentText("M")
        self.ed_blood_type.clear()
        self.ed_address.clear()
        self.ed_birth_date.setDate(QDate.currentDate())
        self.ed_phone.clear()
        self.ed_emergency_phone.clear()
        self.cb_user_type.setCurrentText("NORMAL")
        self.ed_monitor_target_id.clear()

    def closeEvent(self, event):
        self.list_updated.emit()
        super().closeEvent(event)
