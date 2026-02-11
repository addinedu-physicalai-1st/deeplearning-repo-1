# -*- coding: utf-8 -*-
"""이벤트 조회 관리: emergency_events 검색 및 영상 재생."""

import os
import sys

from PyQt6.QtWidgets import (
    QDialog,
    QVBoxLayout,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QPushButton,
    QTableWidget,
    QTableWidgetItem,
    QComboBox,
    QMessageBox,
    QHeaderView,
)
from PyQt6.QtCore import Qt

_SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
_PROJECT_ROOT = os.path.dirname(_SCRIPT_DIR)
if _PROJECT_ROOT not in sys.path:
    sys.path.insert(0, _PROJECT_ROOT)

from db_client import MySqlClient
from event_video_player_window import EventVideoPlayerWindow


class EventManageWindow(QDialog):
    """이벤트 조회 관리: emergency_events 검색 및 영상 재생."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("이벤트 조회 관리")
        self.setMinimumSize(900, 500)
        self.resize(1000, 600)
        self._db = MySqlClient(base_dir=_SCRIPT_DIR)
        self._init_ui()
        self._load_events()

    def _init_ui(self):
        layout = QVBoxLayout(self)

        # 검색 영역
        search_layout = QHBoxLayout()
        search_layout.addWidget(QLabel("user_id:"))
        self.ed_user_id = QLineEdit()
        self.ed_user_id.setPlaceholderText("검색 (비워두면 전체)")
        search_layout.addWidget(self.ed_user_id)
        search_layout.addWidget(QLabel("event_type:"))
        self.cb_event_type = QComboBox()
        self.cb_event_type.addItems(["전체", "ALERT", "낙상", "쓰러짐"])
        search_layout.addWidget(self.cb_event_type)
        self.btn_search = QPushButton("검색")
        self.btn_search.clicked.connect(self._load_events)
        search_layout.addWidget(self.btn_search)
        self.btn_refresh = QPushButton("새로고침")
        self.btn_refresh.clicked.connect(self._load_events)
        search_layout.addWidget(self.btn_refresh)
        search_layout.addStretch()
        layout.addLayout(search_layout)

        # 테이블
        self.table = QTableWidget()
        self.table.setColumnCount(8)
        self.table.setHorizontalHeaderLabels([
            "event_id", "user_id", "name", "event_type", "message", "received_at", "video_path", "영상 재생"
        ])
        self.table.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.ResizeToContents)
        self.table.horizontalHeader().setSectionResizeMode(4, QHeaderView.ResizeMode.Stretch)
        self.table.horizontalHeader().setSectionResizeMode(6, QHeaderView.ResizeMode.Stretch)
        self.table.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
        layout.addWidget(self.table)

    def _load_events(self):
        user_id = self.ed_user_id.text().strip()
        event_type = self.cb_event_type.currentText()
        if event_type == "전체":
            event_type = None

        conditions = []
        params = []
        if user_id:
            conditions.append("user_id LIKE %s")
            params.append(f"%{user_id}%")
        if event_type:
            conditions.append("event_type = %s")
            params.append(event_type)
        where_clause = " AND ".join(conditions) if conditions else "1=1"
        sql = f"""
            SELECT e.event_id, e.user_id, e.device_id, e.event_type, e.message,
                   e.video_path, e.client_timestamp, e.received_at,
                   u.name, u.phone
            FROM emergency_events e
            LEFT JOIN users u ON e.user_id = u.user_id
            WHERE {where_clause}
            ORDER BY e.received_at DESC
            LIMIT 500
        """

        try:
            rows = self._db.fetch_all(sql, tuple(params) if params else None)
        except Exception as e:
            QMessageBox.warning(self, "오류", f"조회 실패: {e}")
            return

        self.table.setRowCount(len(rows))
        for i, row in enumerate(rows):
            self.table.setItem(i, 0, QTableWidgetItem(str(row.get("event_id") or "")))
            self.table.setItem(i, 1, QTableWidgetItem(str(row.get("user_id") or "")))
            self.table.setItem(i, 2, QTableWidgetItem(str(row.get("name") or "")))
            self.table.setItem(i, 3, QTableWidgetItem(str(row.get("event_type") or "")))
            self.table.setItem(i, 4, QTableWidgetItem(str(row.get("message") or "")))
            recv = row.get("received_at")
            recv_str = recv.strftime("%Y-%m-%d %H:%M:%S") if recv else ""
            self.table.setItem(i, 5, QTableWidgetItem(recv_str))
            video_path = row.get("video_path") or ""
            self.table.setItem(i, 6, QTableWidgetItem(video_path))
            btn = QPushButton("영상 재생")
            btn.setProperty("video_path", video_path)
            btn.setProperty("event_id", row.get("event_id"))
            btn.setEnabled(bool(video_path))
            btn.clicked.connect(self._on_play_clicked)
            self.table.setCellWidget(i, 7, btn)

    def _on_play_clicked(self):
        btn = self.sender()
        if not isinstance(btn, QPushButton):
            return
        video_path = btn.property("video_path") or ""
        if not video_path:
            QMessageBox.warning(self, "오류", "영상 경로가 없습니다.")
            return
        import os
        if not os.path.isfile(video_path):
            QMessageBox.warning(self, "오류", "영상 파일을 찾을 수 없습니다.")
            return
        evt_id = btn.property("event_id")
        title = f"이벤트 영상 재생 (event_id={evt_id})"
        player = EventVideoPlayerWindow(video_path=video_path, title=title, parent=self)
        player.exec()
