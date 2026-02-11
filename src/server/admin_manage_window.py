# -*- coding: utf-8 -*-
"""
관리자 관리 창 - admin_users 테이블 연동.

추가/수정/삭제 기능 제공.
"""

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
    QMessageBox,
    QTableWidget,
    QTableWidgetItem,
    QAbstractItemView,
    QCheckBox,
)
from PyQt6.QtCore import Qt

_SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
_PROJECT_ROOT = os.path.dirname(_SCRIPT_DIR)
if _PROJECT_ROOT not in sys.path:
    sys.path.insert(0, _PROJECT_ROOT)

from db_client import MySqlClient


class AdminManageWindow(QDialog):
    """관리자 추가/수정/삭제 창. admin_users 테이블 연동."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("관리자 관리")
        self.setMinimumSize(640, 480)
        self.resize(760, 560)
        self._db = MySqlClient(base_dir=_SCRIPT_DIR)
        self._init_ui()
        self._center_on_screen()
        self._load_admins()

    def _init_ui(self):
        layout = QVBoxLayout(self)
        title = QLabel("관리자 관리 (admin_users)")
        title.setAlignment(Qt.AlignmentFlag.AlignCenter)
        title.setStyleSheet("font-weight: bold; font-size: 14px;")
        layout.addWidget(title)

        form = QFormLayout()
        self.ed_admin_no = QLineEdit()
        self.ed_admin_no.setReadOnly(True)
        self.ed_admin_no.setPlaceholderText("추가 시 자동")
        self.ed_admin_id = QLineEdit()
        self.ed_admin_id.setPlaceholderText("관리자 ID")
        self.ed_admin_pw = QLineEdit()
        self.ed_admin_pw.setEchoMode(QLineEdit.EchoMode.Password)
        self.ed_admin_pw.setPlaceholderText("비밀번호 (수정 시 비워두면 변경 안 함)")
        self.cb_admin_role = QComboBox()
        self.cb_admin_role.addItems(["Master", "Manager", "Viewer"])
        self.cb_is_active = QCheckBox("활성화")
        self.cb_is_active.setChecked(True)

        form.addRow("admin_no", self.ed_admin_no)
        form.addRow("admin_id*", self.ed_admin_id)
        form.addRow("admin_pw*", self.ed_admin_pw)
        form.addRow("admin_role", self.cb_admin_role)
        form.addRow("is_active", self.cb_is_active)
        layout.addLayout(form)

        btn_layout = QHBoxLayout()
        self.btn_add = QPushButton("관리자 추가")
        self.btn_edit = QPushButton("관리자 수정")
        self.btn_delete = QPushButton("관리자 삭제")
        self.btn_refresh = QPushButton("새로고침")
        self.btn_clear = QPushButton("입력 초기화")
        btn_layout.addWidget(self.btn_add)
        btn_layout.addWidget(self.btn_edit)
        btn_layout.addWidget(self.btn_delete)
        btn_layout.addWidget(self.btn_refresh)
        btn_layout.addWidget(self.btn_clear)
        layout.addLayout(btn_layout)

        self.table = QTableWidget(0, 5)
        self.table.setHorizontalHeaderLabels(
            ["admin_no", "admin_id", "admin_role", "is_active", "created_at"]
        )
        self.table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self.table.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        self.table.itemSelectionChanged.connect(self._on_select_row)
        layout.addWidget(self.table, 1)

        self.btn_close = QPushButton("닫기")
        self.btn_close.clicked.connect(self.close)
        layout.addWidget(self.btn_close, alignment=Qt.AlignmentFlag.AlignRight)

        self.btn_add.clicked.connect(self._add_admin)
        self.btn_edit.clicked.connect(self._update_admin)
        self.btn_delete.clicked.connect(self._delete_admin)
        self.btn_refresh.clicked.connect(self._load_admins)
        self.btn_clear.clicked.connect(self._clear_form)

    def _center_on_screen(self):
        screen = self.screen()
        if screen is None:
            return
        geo = screen.availableGeometry()
        frame = self.frameGeometry()
        frame.moveCenter(geo.center())
        self.move(frame.topLeft())

    def _load_admins(self):
        try:
            rows = self._db.fetch_all(
                "SELECT admin_no, admin_id, admin_role, is_active, created_at "
                "FROM admin_users ORDER BY admin_no ASC"
            )
        except Exception as exc:
            QMessageBox.critical(
                self, "DB 오류", f"관리자 목록을 불러오지 못했습니다.\n{exc}"
            )
            return
        self.table.setRowCount(0)
        for row in rows:
            r = self.table.rowCount()
            self.table.insertRow(r)
            for c, key in enumerate(
                ["admin_no", "admin_id", "admin_role", "is_active", "created_at"]
            ):
                val = row.get(key)
                if val is None:
                    text = ""
                elif isinstance(val, bool) or (isinstance(val, int) and key == "is_active"):
                    text = "Y" if val else "N"
                else:
                    text = str(val)
                self.table.setItem(r, c, QTableWidgetItem(text))

    def _on_select_row(self):
        row = self.table.currentRow()
        if row < 0:
            return
        self.ed_admin_no.setText(self.table.item(row, 0).text())
        self.ed_admin_id.setText(self.table.item(row, 1).text())
        self.ed_admin_pw.clear()  # 보안상 비밀번호는 표시하지 않음
        self.cb_admin_role.setCurrentText(self.table.item(row, 2).text() or "Manager")
        active = self.table.item(row, 3).text()
        self.cb_is_active.setChecked(active.upper() in ("Y", "1", "TRUE"))

    def _add_admin(self):
        admin_id = self.ed_admin_id.text().strip()
        admin_pw = self.ed_admin_pw.text().strip()
        if not admin_id:
            QMessageBox.warning(self, "입력 오류", "admin_id는 필수입니다.")
            return
        if not admin_pw:
            QMessageBox.warning(self, "입력 오류", "admin_pw는 필수입니다.")
            return
        try:
            exists = self._db.fetch_one(
                "SELECT admin_id FROM admin_users WHERE admin_id=%s", (admin_id,)
            )
        except Exception as exc:
            QMessageBox.critical(self, "DB 오류", f"중복 확인에 실패했습니다.\n{exc}")
            return
        if exists:
            QMessageBox.warning(self, "중복", "이미 존재하는 admin_id입니다.")
            return
        try:
            self._db.insert(
                "admin_users",
                {
                    "admin_id": admin_id,
                    "admin_pw": admin_pw,
                    "admin_role": self.cb_admin_role.currentText(),
                    "is_active": 1 if self.cb_is_active.isChecked() else 0,
                },
            )
        except Exception as exc:
            print(f"[AdminManageWindow] 관리자 추가 실패: {exc}")
            QMessageBox.critical(self, "추가 실패", "관리자 추가에 실패했습니다.")
            return
        self._load_admins()
        self._clear_form()

    def _update_admin(self):
        admin_no = self.ed_admin_no.text().strip()
        if not admin_no:
            QMessageBox.warning(self, "선택 필요", "수정할 관리자를 선택해주세요.")
            return
        admin_id = self.ed_admin_id.text().strip()
        if not admin_id:
            QMessageBox.warning(self, "입력 오류", "admin_id는 필수입니다.")
            return

        data = {
            "admin_id": admin_id,
            "admin_role": self.cb_admin_role.currentText(),
            "is_active": 1 if self.cb_is_active.isChecked() else 0,
        }
        admin_pw = self.ed_admin_pw.text().strip()
        if admin_pw:
            data["admin_pw"] = admin_pw

        try:
            self._db.update(
                "admin_users",
                data,
                "admin_no=%s",
                (admin_no,),
            )
        except Exception as exc:
            QMessageBox.critical(self, "DB 오류", f"관리자 수정에 실패했습니다.\n{exc}")
            return
        self._load_admins()

    def _delete_admin(self):
        admin_no = self.ed_admin_no.text().strip()
        if not admin_no:
            QMessageBox.warning(self, "선택 필요", "삭제할 관리자를 선택해주세요.")
            return
        if (
            QMessageBox.question(
                self, "삭제 확인", "선택한 관리자를 삭제할까요?"
            )
            != QMessageBox.StandardButton.Yes
        ):
            return
        try:
            self._db.delete("admin_users", "admin_no=%s", (admin_no,))
        except Exception as exc:
            QMessageBox.critical(self, "DB 오류", f"관리자 삭제에 실패했습니다.\n{exc}")
            return
        self._load_admins()
        self._clear_form()

    def _clear_form(self):
        self.ed_admin_no.clear()
        self.ed_admin_id.clear()
        self.ed_admin_pw.clear()
        self.cb_admin_role.setCurrentText("Manager")
        self.cb_is_active.setChecked(True)
