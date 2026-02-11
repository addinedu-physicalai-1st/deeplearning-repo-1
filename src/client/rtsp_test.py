#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
RTSP 스트림 연결 및 재생 테스트 프로그램 (PyQt6 + OpenCV)

- RTSP URL 입력 후 연결 여부 확인
- 연결된 경우 영상이 정상 재생되는지 확인
"""

import sys
import cv2
from PyQt6.QtCore import Qt, QTimer
from PyQt6.QtGui import QImage, QPixmap, QFont
from PyQt6.QtWidgets import (
    QApplication,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMainWindow,
    QPushButton,
    QVBoxLayout,
    QWidget,
)


def cv2_frame_to_qimage(frame):
    """OpenCV BGR 프레임을 QImage(RGB)로 변환."""
    if frame is None:
        return QImage()
    h, w, ch = frame.shape
    bytes_per_line = ch * w
    rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
    return QImage(rgb.data, w, h, bytes_per_line, QImage.Format.Format_RGB888)


class RtspTestWindow(QMainWindow):
    """RTSP 테스트 창. wizard_mode=True 시 InitWindow에서 사용 (이 URL로 사용 / RTSP 사용 안 함)."""

    def __init__(self, parent=None, wizard_mode: bool = False):
        super().__init__(parent)
        self.wizard_mode = wizard_mode
        self.wizard_result: tuple[bool, str] | None = None  # (rtsp_enable, rtsp_url)
        self.cap = None
        self.is_running = False
        self.frame_count = 0
        self.timer = QTimer(self)
        self.timer.timeout.connect(self.update_frame)

        self.setWindowTitle("RTSP 연결/재생 테스트")
        self.setMinimumSize(640, 560)
        self.resize(800, 660)
        self._init_ui()
        self._set_status_idle()

    def _init_ui(self):
        central = QWidget(self)
        self.setCentralWidget(central)
        layout = QVBoxLayout(central)

        # RTSP URL 입력
        url_row = QHBoxLayout()
        url_row.addWidget(QLabel("RTSP URL:"))
        self.url_edit = QLineEdit(self)
        self.url_edit.setPlaceholderText("예: rtsp://user:pass@192.168.0.10:554/stream1")
        self.url_edit.setMinimumWidth(320)
        self.url_edit.returnPressed.connect(self.test_connection)
        url_row.addWidget(self.url_edit)
        layout.addLayout(url_row)

        # 상태 영역
        self.status_label = QLabel("RTSP URL을 입력한 뒤 '연결 테스트'를 누르세요.")
        self.status_label.setFont(QFont("", 12, QFont.Weight.Bold))
        self.status_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.status_label.setStyleSheet(
            "padding: 8px; background-color: #2d2d2d; color: #eee; border-radius: 4px;"
        )
        layout.addWidget(self.status_label)

        # 영상 표시 영역
        self.video_label = QLabel("영상이 여기에 표시됩니다.")
        self.video_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.video_label.setMinimumSize(640, 360)
        self.video_label.setStyleSheet(
            "background-color: #1a1a1a; color: #666; font-size: 14px;"
        )
        layout.addWidget(self.video_label, 1)

        # 재생 정보 (프레임 수)
        self.info_label = QLabel("")
        self.info_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.info_label.setStyleSheet("color: #888;")
        layout.addWidget(self.info_label)

        # 버튼
        btn_layout = QHBoxLayout()
        btn_layout.addStretch()
        self.test_btn = QPushButton("연결 테스트")
        self.test_btn.clicked.connect(self.test_connection)
        self.start_btn = QPushButton("재생 시작")
        self.start_btn.clicked.connect(self.toggle_stream)
        self.start_btn.setEnabled(False)
        btn_layout.addWidget(self.test_btn)
        btn_layout.addWidget(self.start_btn)
        if self.wizard_mode:
            self.use_btn = QPushButton("이 URL로 사용")
            self.use_btn.setEnabled(False)
            self.use_btn.clicked.connect(self._on_use_rtsp)
            self.skip_btn = QPushButton("RTSP 사용 안 함")
            self.skip_btn.clicked.connect(self._on_skip_rtsp)
            btn_layout.addWidget(self.use_btn)
            btn_layout.addWidget(self.skip_btn)
        btn_layout.addStretch()
        layout.addLayout(btn_layout)

    def _on_use_rtsp(self):
        """이 URL로 사용: 연결 성공 상태에서만 호출."""
        if self.is_running:
            self.timer.stop()
            self.is_running = False
        self._release_capture()
        url = self._current_url()
        self.wizard_result = (True, url)
        self.close()

    def _on_skip_rtsp(self):
        """RTSP 사용 안 함."""
        if self.is_running:
            self.timer.stop()
            self.is_running = False
        self._release_capture()
        self.wizard_result = (False, "")
        self.close()

    def _set_status_idle(self):
        self.status_label.setText("RTSP URL을 입력한 뒤 '연결 테스트'를 누르세요.")
        self.status_label.setStyleSheet(
            "padding: 8px; background-color: #2d2d2d; color: #eee; border-radius: 4px;"
        )
        self.video_label.setText("영상이 여기에 표시됩니다.")
        self.start_btn.setEnabled(False)

    def _release_capture(self):
        if self.cap is not None:
            try:
                self.cap.release()
            except Exception:
                pass
            self.cap = None

    def _current_url(self) -> str:
        url = (self.url_edit.text() or "").strip()
        return url

    def test_connection(self):
        """입력한 RTSP URL로 연결 시도 후, 한 프레임 읽기까지 확인."""
        if self.is_running:
            self.timer.stop()
            self.is_running = False
            self.start_btn.setText("재생 시작")
        self._release_capture()
        self.video_label.clear()
        self.video_label.setText("연결 시도 중...")
        self.info_label.setText("")
        QApplication.processEvents()

        url = self._current_url()
        if not url:
            self.status_label.setText("✗ RTSP URL을 입력하세요.")
            self.status_label.setStyleSheet(
                "padding: 8px; background-color: #5c1a1a; color: #eee; border-radius: 4px;"
            )
            self.video_label.setText("RTSP URL을 입력한 뒤 '연결 테스트'를 누르세요.")
            self.start_btn.setEnabled(False)
            return

        if not url.lower().startswith("rtsp://"):
            self.status_label.setText("✗ URL은 rtsp:// 로 시작해야 합니다.")
            self.status_label.setStyleSheet(
                "padding: 8px; background-color: #5c1a1a; color: #eee; border-radius: 4px;"
            )
            self.video_label.setText("예: rtsp://user:pass@192.168.0.10:554/stream1")
            self.start_btn.setEnabled(False)
            return

        # RTSP는 연결이 느릴 수 있으므로 CAP_FFMPEG 사용 (기본값)
        self.cap = cv2.VideoCapture(url, cv2.CAP_FFMPEG)
        if self.cap is None or not self.cap.isOpened():
            self._release_capture()
            self.status_label.setText("✗ RTSP 연결 실패 — URL·네트워크·인증을 확인하세요.")
            self.status_label.setStyleSheet(
                "padding: 8px; background-color: #5c1a1a; color: #eee; border-radius: 4px;"
            )
            self.video_label.setText("연결 실패. URL, 포트, 아이디/비밀번호, 방화벽을 확인하세요.")
            self.start_btn.setEnabled(False)
            return

        ret, frame = self.cap.read()
        if not ret or frame is None:
            self._release_capture()
            self.status_label.setText("⚠ 스트림은 열렸으나 프레임을 읽을 수 없음")
            self.status_label.setStyleSheet(
                "padding: 8px; background-color: #6d5a00; color: #eee; border-radius: 4px;"
            )
            self.video_label.setText("프레임 읽기 실패. 스트림이 비어 있거나 코덱을 확인하세요.")
            self.start_btn.setEnabled(False)
            return

        self.status_label.setText("✓ RTSP 연결됨 — 영상 입력 정상")
        self.status_label.setStyleSheet(
            "padding: 8px; background-color: #1b4d1b; color: #eee; border-radius: 4px;"
        )
        self.video_label.setText("'재생 시작' 버튼을 눌러 영상 재생을 확인하세요.")
        self.start_btn.setEnabled(True)
        self.info_label.setText("연결 성공. 재생 시작을 눌러 주세요.")
        if getattr(self, "wizard_mode", False) and getattr(self, "use_btn", None):
            self.use_btn.setEnabled(True)

    def toggle_stream(self):
        url = self._current_url()
        if not url or self.cap is None or not self.cap.isOpened():
            return
        if self.is_running:
            self.timer.stop()
            self.is_running = False
            self.start_btn.setText("재생 시작")
            self.info_label.setText("일시정지됨.")
        else:
            self.frame_count = 0
            self.timer.start(33)
            self.is_running = True
            self.start_btn.setText("재생 중지")

    def update_frame(self):
        if self.cap is None or not self.cap.isOpened():
            return
        ret, frame = self.cap.read()
        if not ret or frame is None:
            self.info_label.setText("프레임 읽기 실패 — 재생이 제대로 되지 않습니다.")
            return
        self.frame_count += 1
        qimg = cv2_frame_to_qimage(frame)
        pixmap = QPixmap.fromImage(qimg)
        scaled = pixmap.scaled(
            self.video_label.size(),
            Qt.AspectRatioMode.KeepAspectRatio,
            Qt.TransformationMode.SmoothTransformation,
        )
        self.video_label.setPixmap(scaled)
        self.video_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.info_label.setText(f"정상 재생 중 (수신 프레임: {self.frame_count})")

    def closeEvent(self, event):
        self.timer.stop()
        self._release_capture()
        if getattr(self, "wizard_mode", False) and self.wizard_result is None:
            self.wizard_result = (False, "")
        event.accept()


def main():
    app = QApplication(sys.argv)
    win = RtspTestWindow()
    win.show()
    sys.exit(app.exec())


if __name__ == "__main__":
    main()
