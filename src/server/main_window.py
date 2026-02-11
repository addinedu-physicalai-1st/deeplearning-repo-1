# -*- coding: utf-8 -*-
"""
MainWindow: VMS 서버 메인 화면 (main_windows.ui 로드).

상용 VMS 서버 화면과 동일한 틀:
- 메뉴 영역 (menu_area)
- 디바이스 장치 리스트 (device_list_panel, device_list_widget)
- N×N 격자타일 영상 영역 (grid_area, grid_layout) — client/엣지박스 영상 수신용
- 이벤트 수신 리스트 (event_list_panel, event_list_widget)

역할: client/main_window.py ↔ server/main_window.py 통신으로 AI 엣지박스 감시·관리 서버.
"""

import os
import sys
from PyQt6 import uic
from PyQt6.QtWidgets import (
    QMainWindow,
    QMenu,
    QToolButton,
    QListWidgetItem,
    QFrame,
    QVBoxLayout,
    QLabel,
    QPushButton,
    QInputDialog,
)
from PyQt6.QtGui import QColor, QImage, QPixmap
from PyQt6.QtCore import QTimer, Qt

_SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
_PROJECT_ROOT = os.path.dirname(_SCRIPT_DIR)
if _PROJECT_ROOT not in sys.path:
    sys.path.insert(0, _PROJECT_ROOT)

from admin_manage_window import AdminManageWindow
from user_manage_window import UserManageWindow
from event_manage_window import EventManageWindow
from db_client import MySqlClient
from api_server import start_api_server, get_keepalive_status, get_latest_frame, pop_alarm
from alarm_popup_window import AlarmPopupWindow


class MainWindow(QMainWindow):
    """VMS 서버 메인. UI: main_windows.ui. 영상/이벤트는 이후 통신 로직으로 채움."""

    def __init__(self, parent=None):
        super().__init__(parent)
        ui_path = os.path.join(_SCRIPT_DIR, "main_windows.ui")
        uic.loadUi(ui_path, self)
        self._setup_ui()

    def _setup_ui(self):
        """UI 로드 후 초기화·시그널 연결. device_list_widget, grid_layout, event_list_widget 사용."""
        if hasattr(self, "menubar"):
            self.menubar.setVisible(False)

        self._admin_manage_win = None
        self._user_manage_win = None
        self._event_manage_win = None
        self._db = MySqlClient(base_dir=_SCRIPT_DIR)
        start_api_server()
        self._keepalive_timer = QTimer(self)
        self._keepalive_timer.timeout.connect(self._load_user_list)
        self._keepalive_timer.start(3000)
        self._grid_cells = []
        self._build_grid_cells()
        self._video_timer = QTimer(self)
        self._video_timer.timeout.connect(self._refresh_grid_frames)
        self._video_timer.start(100)
        self._alarm_timer = QTimer(self)
        self._alarm_timer.timeout.connect(self._poll_alarm)
        self._alarm_timer.start(500)
        # 클라이언트별 알람 팝업 1개만 유지 (user_id 기준)
        self._active_alarm_popups: dict[str, AlarmPopupWindow] = {}

        if hasattr(self, "manage_menu_button"):
            menu = QMenu(self)
            act_admin = menu.addAction("관리자 관리")
            act_user = menu.addAction("사용자 관리")
            act_event = menu.addAction("이벤트 조회 관리")
            act_admin.triggered.connect(self._open_admin_manage)
            act_user.triggered.connect(self._open_user_manage)
            act_event.triggered.connect(self._open_event_manage)
            self.manage_menu_button.setMenu(menu)
            self.manage_menu_button.setPopupMode(QToolButton.ToolButtonPopupMode.MenuButtonPopup)

        self._load_user_list()

    def _open_admin_manage(self):
        if self._admin_manage_win is None or not self._admin_manage_win.isVisible():
            self._admin_manage_win = AdminManageWindow(self)
        self._admin_manage_win.show()
        self._admin_manage_win.raise_()
        self._admin_manage_win.activateWindow()

    def _open_user_manage(self):
        if self._user_manage_win is None or not self._user_manage_win.isVisible():
            self._user_manage_win = UserManageWindow(self)
            self._user_manage_win.list_updated.connect(self._load_user_list)
        self._user_manage_win.show()
        self._user_manage_win.raise_()
        self._user_manage_win.activateWindow()

    def _open_event_manage(self):
        if self._event_manage_win is None or not self._event_manage_win.isVisible():
            self._event_manage_win = EventManageWindow(self)
        self._event_manage_win.show()
        self._event_manage_win.raise_()
        self._event_manage_win.activateWindow()

    def _build_grid_cells(self):
        if hasattr(self, "grid_placeholder"):
            self.grid_placeholder.hide()
        for i in range(4):
            for j in range(4):
                frame = QFrame(self)
                frame.setStyleSheet("background-color: #1f1f1f; border: 1px solid #333;")
                vbox = QVBoxLayout(frame)
                vbox.setContentsMargins(4, 4, 4, 4)
                title = QLabel("미지정")
                title.setAlignment(Qt.AlignmentFlag.AlignCenter)
                title.setStyleSheet("color: #eee; font-weight: bold;")
                video = QLabel("영상 없음")
                video.setAlignment(Qt.AlignmentFlag.AlignCenter)
                video.setMinimumSize(160, 120)
                video.setStyleSheet("background-color: #000; color: #666;")
                btn = QPushButton("모니터링")
                vbox.addWidget(title)
                vbox.addWidget(video, 1)
                vbox.addWidget(btn)
                self.grid_layout.addWidget(frame, i, j)
                cell = {"frame": frame, "title": title, "video": video, "btn": btn, "user_id": None}
                btn.clicked.connect(lambda _=False, c=cell: self._toggle_monitor(c))
                self._grid_cells.append(cell)

    def _toggle_monitor(self, cell: dict):
        if cell["user_id"]:
            cell["user_id"] = None
            cell["title"].setText("미지정")
            cell["btn"].setText("모니터링")
            cell["video"].setText("영상 없음")
            cell["video"].setPixmap(QPixmap())
            return

        index_no = self._get_selected_index_no()
        if not index_no:
            index_no, ok = QInputDialog.getText(self, "모니터링 설정", "index_no 입력:")
            if not ok:
                return
            index_no = index_no.strip()
        if not index_no:
            return
        try:
            row = self._db.fetch_one("SELECT user_id FROM users WHERE index_no=%s", (index_no,))
        except Exception:
            row = None
        if not row:
            return
        user_id = row.get("user_id")
        cell["user_id"] = user_id
        cell["title"].setText(user_id)
        cell["btn"].setText("해제")

    def _get_selected_index_no(self):
        if not hasattr(self, "device_list_widget"):
            return None
        item = self.device_list_widget.currentItem()
        if item is None:
            return None
        parts = [p.strip() for p in item.text().split("|")]
        if len(parts) >= 2:
            return parts[1]
        return None

    def _load_user_list(self):
        if not hasattr(self, "device_list_widget"):
            return
        self.device_list_widget.clear()
        try:
            rows = self._db.fetch_all(
                "SELECT index_no, user_id, name, phone FROM users ORDER BY created_at DESC"
            )
        except Exception:
            return
        for row in rows:
            index_no = row.get("index_no") or ""
            user_id = row.get("user_id") or ""
            name = row.get("name") or ""
            phone = row.get("phone") or ""
            is_online = get_keepalive_status(user_id)
            status_text = "ON" if is_online else "OFF"
            text = f"{status_text} | {index_no} | {user_id} | {name} | {phone}"
            item = QListWidgetItem(text)
            if is_online:
                item.setBackground(QColor("#1b5e20"))
                item.setForeground(QColor("#e8f5e9"))
            else:
                item.setBackground(QColor("#7f1d1d"))
                item.setForeground(QColor("#fee2e2"))
            self.device_list_widget.addItem(item)

    def _refresh_grid_frames(self):
        for cell in self._grid_cells:
            user_id = cell.get("user_id")
            if not user_id:
                continue
            frame = get_latest_frame(user_id)
            if frame is None:
                continue
            h, w, ch = frame.shape
            bytes_per_line = ch * w
            qimg = QImage(frame.data, w, h, bytes_per_line, QImage.Format.Format_RGB888)
            pix = QPixmap.fromImage(qimg).scaled(
                cell["video"].width(),
                cell["video"].height(),
                Qt.AspectRatioMode.KeepAspectRatio,
                Qt.TransformationMode.SmoothTransformation,
            )
            cell["video"].setPixmap(pix)

    def _append_event_to_list(self, data: dict, user_id: str):
        """메인 화면 하단 이벤트 리스트에 항목 추가."""
        if not hasattr(self, "event_list_widget"):
            return
        ts = data.get("received_at") or data.get("timestamp") or ""
        msg = data.get("message") or ""
        evt_type = data.get("event_type") or "ALERT"
        text = f"[{ts}] {user_id} | {evt_type} | {msg}"
        item = QListWidgetItem(text)
        self.event_list_widget.insertItem(0, item)
        self.event_list_widget.scrollToTop()

    def _poll_alarm(self):
        data = pop_alarm()
        if not data:
            return
        device_id = data.get("device_id")
        user_id = data.get("user_id")
        if not user_id and device_id:
            try:
                row = self._db.fetch_one("SELECT user_id FROM users WHERE device_id=%s", (device_id,))
            except Exception:
                row = None
            if row:
                user_id = row.get("user_id")
        if not user_id:
            user_id = device_id or "unknown"

        # 클라이언트별 알람창 1개만: 이미 있으면 리스트에 Add, 없으면 새로 생성
        popup = self._active_alarm_popups.get(user_id)
        if popup is not None:
            if popup.isVisible():
                popup.add_event(data)
                self._append_event_to_list(data, user_id)
                popup.raise_()
                popup.activateWindow()
                return
            # 닫혀 있으면 제거 후 새로 생성
            del self._active_alarm_popups[user_id]

        self._append_event_to_list(data, user_id)
        popup = AlarmPopupWindow(user_id=user_id, payload=data, db=self._db, parent=self)
        popup.finished.connect(lambda uid=user_id: self._active_alarm_popups.pop(uid, None))
        self._active_alarm_popups[user_id] = popup
        popup.show()
        popup.raise_()
        popup.activateWindow()
