#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
웹캠 연결 및 재생 테스트 프로그램 (PyQt6 + OpenCV)

- 여러 대의 캠을 방어적으로 탐지
- 같은 장치가 인덱스 0/1처럼 두 번 잡히는 경우 하나로 합침 (중복 제거)
- 선택한 캠의 연결 여부·영상 재생 확인
"""

import sys
import cv2
from PyQt6.QtCore import Qt, QTimer
from PyQt6.QtGui import QImage, QPixmap, QFont
from PyQt6.QtWidgets import (
    QApplication,
    QComboBox,
    QHBoxLayout,
    QLabel,
    QMainWindow,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

MAX_CAMERA_INDEX = 31
MAX_CONSECUTIVE_FAILURES = 5


def probe_available_cameras() -> list[int]:
    """
    사용 가능한 카메라 인덱스 목록을 탐지.
    - 각 인덱스로 열고, 한 프레임 읽기까지 성공한 경우만 '사용 가능'으로 간주.
    - 같은 물리 장치가 인덱스 0과 1처럼 두 번 잡히는 경우(연속 인덱스 + 동일 해상도) 하나만 남김.
    """
    raw: list[tuple[int, int, int]] = []  # (index, width, height)
    consecutive_failures = 0
    for index in range(MAX_CAMERA_INDEX + 1):
        cap = None
        try:
            cap = cv2.VideoCapture(index)
            if not cap.isOpened():
                consecutive_failures += 1
                if consecutive_failures >= MAX_CONSECUTIVE_FAILURES:
                    break
                continue
            ret, frame = cap.read()
            if ret and frame is not None:
                h, w = frame.shape[:2]
                raw.append((index, w, h))
                consecutive_failures = 0
            else:
                consecutive_failures += 1
        except Exception:
            consecutive_failures += 1
        finally:
            if cap is not None:
                cap.release()
                cap = None
        if consecutive_failures >= MAX_CONSECUTIVE_FAILURES:
            break

    # 같은 장치 중복 제거: 연속한 인덱스(i, i+1)이고 해상도가 같으면 앞쪽(i)만 유지
    deduped: list[int] = []
    for i, (idx, w, h) in enumerate(raw):
        if i == 0:
            deduped.append(idx)
            continue
        prev_idx, prev_w, prev_h = raw[i - 1]
        if idx == prev_idx + 1 and w == prev_w and h == prev_h:
            # 연속 인덱스 + 동일 해상도 → 같은 장치로 간주, 스킵
            continue
        deduped.append(idx)
    return deduped


def cv2_frame_to_qimage(frame):
    """OpenCV BGR 프레임을 QImage(RGB)로 변환."""
    if frame is None:
        return QImage()
    h, w, ch = frame.shape
    bytes_per_line = ch * w
    rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
    return QImage(rgb.data, w, h, bytes_per_line, QImage.Format.Format_RGB888)


class WebcamTestWindow(QMainWindow):
    """웹캠 테스트 창. wizard_mode=True 시 InitWindow에서 사용 (웹캠 사용 / 웹캠 사용 안 함)."""

    def __init__(self, parent=None, wizard_mode: bool = False):
        super().__init__(parent)
        self.wizard_mode = wizard_mode
        self.wizard_result: bool | None = None  # webcam_enable
        self.cap = None
        self.is_running = False
        self.frame_count = 0
        self.available_indices: list[int] = []
        self.timer = QTimer(self)
        self.timer.timeout.connect(self.update_frame)

        self.setWindowTitle("웹캠 연결/재생 테스트 (다중 캠)")
        self.setMinimumSize(640, 560)
        self.resize(800, 660)
        self._init_ui()
        self.scan_and_select_cameras()

    def _init_ui(self):
        central = QWidget(self)
        self.setCentralWidget(central)
        layout = QVBoxLayout(central)

        cam_row = QHBoxLayout()
        cam_row.addWidget(QLabel("캠 선택:"))
        self.camera_combo = QComboBox(self)
        self.camera_combo.setMinimumWidth(120)
        self.camera_combo.currentIndexChanged.connect(self.on_camera_selection_changed)
        cam_row.addWidget(self.camera_combo)
        cam_row.addStretch()
        layout.addLayout(cam_row)

        self.status_label = QLabel("검사 중...")
        self.status_label.setFont(QFont("", 12, QFont.Weight.Bold))
        self.status_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.status_label.setStyleSheet(
            "padding: 8px; background-color: #2d2d2d; color: #eee; border-radius: 4px;"
        )
        layout.addWidget(self.status_label)

        self.video_label = QLabel("영상이 여기에 표시됩니다.")
        self.video_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.video_label.setMinimumSize(640, 360)
        self.video_label.setStyleSheet(
            "background-color: #1a1a1a; color: #666; font-size: 14px;"
        )
        layout.addWidget(self.video_label, 1)

        self.info_label = QLabel("")
        self.info_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.info_label.setStyleSheet("color: #888;")
        layout.addWidget(self.info_label)

        btn_layout = QHBoxLayout()
        btn_layout.addStretch()
        self.recheck_btn = QPushButton("전체 캠 다시 검사")
        self.recheck_btn.clicked.connect(self.scan_and_select_cameras)
        self.start_btn = QPushButton("재생 시작")
        self.start_btn.clicked.connect(self.toggle_stream)
        self.start_btn.setEnabled(False)
        btn_layout.addWidget(self.recheck_btn)
        btn_layout.addWidget(self.start_btn)
        if self.wizard_mode:
            self.use_btn = QPushButton("웹캠 사용")
            self.use_btn.setEnabled(False)
            self.use_btn.clicked.connect(self._on_use_webcam)
            self.skip_btn = QPushButton("웹캠 사용 안 함")
            self.skip_btn.clicked.connect(self._on_skip_webcam)
            btn_layout.addWidget(self.use_btn)
            btn_layout.addWidget(self.skip_btn)
        btn_layout.addStretch()
        layout.addLayout(btn_layout)

    def _on_use_webcam(self):
        if self.is_running:
            self.timer.stop()
            self.is_running = False
        self._release_camera()
        self.wizard_result = True
        self.close()

    def _on_skip_webcam(self):
        if self.is_running:
            self.timer.stop()
            self.is_running = False
        self._release_camera()
        self.wizard_result = False
        self.close()

    def scan_and_select_cameras(self):
        if self.is_running:
            self.timer.stop()
            self.is_running = False
            self.start_btn.setText("재생 시작")
        self._release_camera()
        self.video_label.clear()
        self.video_label.setText("캠 검색 중...")
        self.info_label.setText("")
        QApplication.processEvents()

        self.available_indices = probe_available_cameras()
        self.camera_combo.clear()
        if not self.available_indices:
            self.camera_combo.addItem("(캠 없음)", -1)
            self.status_label.setText("✗ 사용 가능한 캠 없음 — 장치를 연결한 뒤 '전체 캠 다시 검사'를 누르세요.")
            self.status_label.setStyleSheet(
                "padding: 8px; background-color: #5c1a1a; color: #eee; border-radius: 4px;"
            )
            self.video_label.setText("웹캠을 연결한 뒤 '전체 캠 다시 검사'를 누르세요.")
            self.start_btn.setEnabled(False)
            return
        for idx in self.available_indices:
            self.camera_combo.addItem(f"캠 {idx}", idx)
        self.camera_combo.setCurrentIndex(0)
        self._check_current_camera()
        if len(self.available_indices) == 1:
            self.info_label.setText("캠 1개 감지됨. (같은 장치가 여러 인덱스로 잡힌 경우 자동으로 하나로 합쳐집니다.)")

    def _current_camera_index(self) -> int | None:
        data = self.camera_combo.currentData()
        if data is None or (isinstance(data, int) and data < 0):
            return None
        return int(data)

    def on_camera_selection_changed(self):
        if self.camera_combo.count() == 0:
            return
        if self.is_running:
            self.timer.stop()
            self.is_running = False
            self.start_btn.setText("재생 시작")
        self._release_camera()
        self.video_label.clear()
        self.video_label.setText("영상이 여기에 표시됩니다.")
        self.info_label.setText("")
        idx = self._current_camera_index()
        if idx is None:
            self.status_label.setText("캠을 선택하세요.")
            self.start_btn.setEnabled(False)
            return
        self._check_current_camera()

    def _release_camera(self):
        if self.cap is not None:
            try:
                self.cap.release()
            except Exception:
                pass
            self.cap = None

    def _check_current_camera(self):
        idx = self._current_camera_index()
        if idx is None:
            self.status_label.setText("캠을 선택하세요.")
            self.start_btn.setEnabled(False)
            return
        self._release_camera()
        self.cap = cv2.VideoCapture(idx)
        if self.cap is None or not self.cap.isOpened():
            self.status_label.setText(f"✗ 캠 {idx} 열기 실패 — 장치/권한을 확인하세요.")
            self.status_label.setStyleSheet(
                "padding: 8px; background-color: #5c1a1a; color: #eee; border-radius: 4px;"
            )
            self.start_btn.setEnabled(False)
            return
        ret, frame = self.cap.read()
        if not ret or frame is None:
            self._release_camera()
            self.status_label.setText(f"⚠ 캠 {idx}는 열렸으나 프레임을 읽을 수 없음")
            self.status_label.setStyleSheet(
                "padding: 8px; background-color: #6d5a00; color: #eee; border-radius: 4px;"
            )
            self.video_label.setText("프레임 읽기 실패. 드라이버/권한을 확인하세요.")
            self.start_btn.setEnabled(False)
            return
        self.status_label.setText(
            f"✓ 캠 {idx} 연결됨 — 영상 입력 정상 (장치 {len(self.available_indices)}개)"
        )
        self.status_label.setStyleSheet(
            "padding: 8px; background-color: #1b4d1b; color: #eee; border-radius: 4px;"
        )
        self.video_label.setText("'재생 시작' 버튼을 눌러 영상 재생을 확인하세요.")
        self.start_btn.setEnabled(True)
        if getattr(self, "wizard_mode", False) and getattr(self, "use_btn", None):
            self.use_btn.setEnabled(True)

    def toggle_stream(self):
        idx = self._current_camera_index()
        if idx is None or self.cap is None or not self.cap.isOpened():
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
        idx = self._current_camera_index()
        self.info_label.setText(f"캠 {idx} 정상 재생 중 (수신 프레임: {self.frame_count})")

    def closeEvent(self, event):
        self.timer.stop()
        self._release_camera()
        if getattr(self, "wizard_mode", False) and self.wizard_result is None:
            self.wizard_result = False
        event.accept()


def main():
    app = QApplication(sys.argv)
    win = WebcamTestWindow()
    win.show()
    sys.exit(app.exec())


if __name__ == "__main__":
    main()
