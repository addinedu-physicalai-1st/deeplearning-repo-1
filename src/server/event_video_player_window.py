# -*- coding: utf-8 -*-
"""영상 재생 팝업: emergency_events에 저장된 영상 파일 재생."""

import os
import sys
import cv2

from PyQt6.QtWidgets import QDialog, QVBoxLayout, QLabel, QPushButton
from PyQt6.QtCore import QTimer, Qt
from PyQt6.QtGui import QImage, QPixmap

_SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
_PROJECT_ROOT = os.path.dirname(_SCRIPT_DIR)
if _PROJECT_ROOT not in sys.path:
    sys.path.insert(0, _PROJECT_ROOT)


class EventVideoPlayerWindow(QDialog):
    """저장된 영상 파일 재생."""

    def __init__(self, video_path: str, title: str = "영상 재생", parent=None):
        super().__init__(parent)
        self.setWindowTitle(title)
        self.setMinimumSize(640, 480)
        self.resize(800, 600)
        self._video_path = video_path
        self._cap = None
        self._timer = QTimer(self)
        self._timer.timeout.connect(self._next_frame)
        self._init_ui()

    def _init_ui(self):
        layout = QVBoxLayout(self)
        self.video_label = QLabel("영상 로딩 중...")
        self.video_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.video_label.setMinimumSize(320, 240)
        self.video_label.setStyleSheet("background-color: #000; color: #ccc;")
        layout.addWidget(self.video_label)
        btn_close = QPushButton("닫기")
        btn_close.clicked.connect(self.close)
        layout.addWidget(btn_close)

    def showEvent(self, event):
        super().showEvent(event)
        if not self._video_path or not os.path.isfile(self._video_path):
            self.video_label.setText("영상 파일을 찾을 수 없습니다.")
            return
        self._cap = cv2.VideoCapture(self._video_path)
        if not self._cap.isOpened():
            self.video_label.setText("영상 재생에 실패했습니다.")
            return
        self._timer.start(33)  # ~30fps

    def _next_frame(self):
        if self._cap is None:
            return
        ret, frame = self._cap.read()
        if not ret:
            self._timer.stop()
            self._cap.release()
            self._cap = None
            self.video_label.setText("재생 완료")
            return
        rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
        h, w, ch = rgb.shape
        bytes_per_line = ch * w
        qimg = QImage(rgb.data, w, h, bytes_per_line, QImage.Format.Format_RGB888)
        pix = QPixmap.fromImage(qimg).scaled(
            self.video_label.width(),
            self.video_label.height(),
            Qt.AspectRatioMode.KeepAspectRatio,
            Qt.TransformationMode.SmoothTransformation,
        )
        self.video_label.setPixmap(pix)

    def closeEvent(self, event):
        self._timer.stop()
        if self._cap is not None:
            self._cap.release()
            self._cap = None
        super().closeEvent(event)
