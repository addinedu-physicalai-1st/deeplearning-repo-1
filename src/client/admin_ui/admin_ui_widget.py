"""
gui_ver4 메인 윈도우 구조 - 클라이언트 관리자 탭 임베드용 QWidget
임베드 시: 대시보드+실시간모니터링만 노출, 이벤트/사용자/설정/학습은 숨김
"""

import os
import json
from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QStackedWidget,
    QPushButton, QLabel, QFrame, QMessageBox, QApplication,
)
from PyQt6.QtCore import Qt, QTimer, pyqtSignal
from PyQt6.QtGui import QFont
from datetime import datetime

from .database_models import DatabaseManager


class AdminUiWidget(QWidget):
    """gui_ver4 구조 - 관리자 탭 임베드용"""
    logout_requested = pyqtSignal()

    def __init__(self, user_info: dict, parent=None):
        super().__init__(parent)
        self.user_info = user_info
        self.db = DatabaseManager()
        self.current_page = None
        self.menu_buttons = []
        self.embedded_in_client = bool(os.environ.get("ADMIN_UI_ENV_DIR"))
        self._build_ui()

        self.status_timer = QTimer(self)
        self.status_timer.timeout.connect(self._update_time)
        self.status_timer.start(1000)

    def _build_ui(self):
        main_layout = QHBoxLayout(self)
        main_layout.setContentsMargins(0, 0, 0, 0)
        main_layout.setSpacing(0)

        sidebar = self._create_sidebar()
        main_layout.addWidget(sidebar)
        content_area = self._create_content_area()
        main_layout.addWidget(content_area, 1)

    def _create_sidebar(self) -> QFrame:
        sidebar = QFrame()
        sidebar.setFixedWidth(250)
        sidebar.setStyleSheet("""
            QFrame { background-color: #2c3e50; border-right: 1px solid #34495e; }
            QPushButton { text-align: left; padding: 15px 20px; border: none; background-color: transparent; color: #ecf0f1; font-size: 14px; }
            QPushButton:hover { background-color: #34495e; }
            QPushButton:checked { background-color: #3498db; font-weight: bold; }
        """)
        layout = QVBoxLayout(sidebar)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        # 헤더
        header = QFrame()
        header.setStyleSheet("background-color: #1a252f; padding: 20px;")
        header_layout = QVBoxLayout(header)
        title = QLabel("AI Care")
        title.setFont(QFont("Arial", 16, QFont.Weight.Bold))
        title.setStyleSheet("color: white;")
        user_name = QLabel(f"{self.user_info.get('name', self.user_info.get('user_id', ''))}님")
        user_name.setStyleSheet("color: #95a5a6; font-size: 12px;")
        user_type = QLabel(f"({self.user_info.get('user_type', '관리자')})")
        user_type.setStyleSheet("color: #7f8c8d; font-size: 11px;")
        header_layout.addWidget(title)
        header_layout.addWidget(user_name)
        header_layout.addWidget(user_type)
        layout.addWidget(header)

        # 메뉴 버튼
        base_items = [
            ("📊  대시보드", "dashboard"),
            ("🎥  실시간 모니터링", "monitoring"),
        ]
        if not self.embedded_in_client:
            base_items.append(("📋  이벤트 로그", "events"))
            if self.user_info.get("user_type") == "관리자":
                base_items.append(("👥  사용자 관리", "users"))
            base_items.append(("⚙️  설정", "settings"))
            if self.user_info.get("user_type") == "관리자":
                base_items.append(("🎓  모델 학습", "training"))

        for label, page_name in base_items:
            btn = QPushButton(label)
            btn.setCheckable(True)
            btn.setChecked(page_name == "dashboard")
            btn.clicked.connect(lambda checked, p=page_name: self._change_page(p))
            self.menu_buttons.append(btn)
            layout.addWidget(btn)

        layout.addStretch()

        # 종료/로그아웃
        logout_text = "🚪  종료" if self.embedded_in_client else "🚪  로그아웃"
        btn_logout = QPushButton(logout_text)
        btn_logout.clicked.connect(self._logout)
        btn_logout.setStyleSheet("QPushButton { background-color: #c0392b; margin: 10px; border-radius: 5px; } QPushButton:hover { background-color: #e74c3c; }")
        layout.addWidget(btn_logout)
        return sidebar

    def _create_content_area(self) -> QWidget:
        content_widget = QWidget()
        layout = QVBoxLayout(content_widget)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        top_bar = self._create_top_bar()
        layout.addWidget(top_bar)

        self.page_stack = QStackedWidget()
        layout.addWidget(self.page_stack)

        from .dashboard_page import DashboardPage
        from .monitoring_page import MonitoringPage
        from .events_page import EventsPage
        from .users_page import UsersPage
        from .settings_page import SettingsPage
        from .training_page import TrainingPage
        from .model_selection_dialog import get_model_config_from_env

        # 0: 대시보드, 1: 모니터링
        self.page_stack.addWidget(DashboardPage(self.user_info, self.db))

        # MonitoringPage: 임베드 시 devices_config + .env USE_MODEL 전달
        input_config = None
        model_config = None
        client_dir = os.environ.get("ADMIN_UI_ENV_DIR")
        if client_dir:
            cfg_path = os.path.join(client_dir, "devices_config.json")
            if os.path.isfile(cfg_path):
                try:
                    with open(cfg_path, "r", encoding="utf-8") as f:
                        cfg = json.load(f)
                    rtsp_enable = cfg.get("rtsp_enable", False)
                    webcam_enable = cfg.get("webcam_enable", False)
                    rtsp_url = (cfg.get("rtsp_url") or "").strip()
                    if rtsp_enable and rtsp_url:
                        input_config = {"type": "camera", "camera_index": 0, "rtsp_url": rtsp_url}
                    elif webcam_enable:
                        input_config = {"type": "camera", "camera_index": 0}
                except Exception:
                    pass
            model_config = get_model_config_from_env()

        self.page_stack.addWidget(
            MonitoringPage(self.user_info, self.db, input_config=input_config, model_config=model_config)
        )

        # 임베드가 아닐 때만 추가 페이지
        if not self.embedded_in_client:
            self.page_stack.addWidget(EventsPage(self.user_info, self.db))
            if self.user_info.get("user_type") == "관리자":
                self.page_stack.addWidget(UsersPage(self.user_info, self.db))
            self.page_stack.addWidget(SettingsPage(self.user_info, self.db))
            if self.user_info.get("user_type") == "관리자":
                self.page_stack.addWidget(TrainingPage())

        return content_widget

    def _create_top_bar(self) -> QFrame:
        top_bar = QFrame()
        top_bar.setFixedHeight(60)
        top_bar.setStyleSheet("QFrame { background-color: white; border-bottom: 1px solid #ddd; }")
        layout = QHBoxLayout(top_bar)
        layout.setContentsMargins(30, 10, 30, 10)
        self.page_title = QLabel("📊 대시보드")
        self.page_title.setFont(QFont("Arial", 16, QFont.Weight.Bold))
        self.page_title.setStyleSheet("color: #2c3e50;")
        self.status_label = QLabel("🟢 시스템 정상")
        self.status_label.setStyleSheet("color: #27ae60; font-size: 12px;")
        self.time_label = QLabel()
        self.time_label.setStyleSheet("color: #7f8c8d; font-size: 12px;")
        self._update_time()
        layout.addWidget(self.page_title)
        layout.addStretch()
        layout.addWidget(self.status_label)
        layout.addWidget(QLabel("  |  "))
        layout.addWidget(self.time_label)
        return top_bar

    def _change_page(self, page_name: str):
        for btn in self.menu_buttons:
            btn.setChecked(False)
        if self.sender():
            self.sender().setChecked(True)

        if self.embedded_in_client:
            page_map = {"dashboard": (0, "📊 대시보드"), "monitoring": (1, "🎥 실시간 모니터링")}
        else:
            is_admin = self.user_info.get("user_type") == "관리자"
            page_map = {
                "dashboard": (0, "📊 대시보드"),
                "monitoring": (1, "🎥 실시간 모니터링"),
                "events": (2, "📋 이벤트 로그"),
                "users": (3, "👥 사용자 관리"),
                "settings": (4 if is_admin else 3, "⚙️ 설정"),
                "training": (5 if is_admin else 4, "🎓 모델 학습"),
            }

        if page_name in page_map:
            index, title = page_map[page_name]
            self.page_stack.setCurrentIndex(index)
            self.page_title.setText(title)
            self.current_page = page_name

    def _update_time(self):
        self.time_label.setText(datetime.now().strftime("%Y-%m-%d %H:%M:%S"))

    def _logout(self):
        if self.embedded_in_client:
            reply = QMessageBox.question(
                self, "종료", "프로그램을 종료하시겠습니까?",
                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
                QMessageBox.StandardButton.No,
            )
            if reply == QMessageBox.StandardButton.Yes:
                app = QApplication.instance()
                if app:
                    app.quit()
        else:
            reply = QMessageBox.question(
                self, "로그아웃", "로그아웃 하시겠습니까?",
                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
                QMessageBox.StandardButton.No,
            )
            if reply == QMessageBox.StandardButton.Yes:
                self.logout_requested.emit()

    def stop_monitoring(self):
        if hasattr(self, "page_stack"):
            for i in range(self.page_stack.count()):
                page = self.page_stack.widget(i)
                if hasattr(page, "stop_monitoring"):
                    page.stop_monitoring()
                if hasattr(page, "cleanup"):
                    page.cleanup()
