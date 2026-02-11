import os
import sys
import json
import threading
import time
from datetime import datetime

import cv2
import numpy as np
from PyQt6.QtWidgets import QDialog, QVBoxLayout, QLabel, QListWidget, QListWidgetItem
from PyQt6.QtCore import QTimer, Qt
from PyQt6.QtGui import QImage, QPixmap

_SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
_PROJECT_ROOT = os.path.dirname(_SCRIPT_DIR)
if _PROJECT_ROOT not in sys.path:
    sys.path.insert(0, _PROJECT_ROOT)

from env_config import read_env_values
from api_server import get_latest_frame
from db_client import MySqlClient

MOV_DIR = os.path.join(_SCRIPT_DIR, "mov")
POPUP_DURATION_SEC = 10
RECORD_DURATION_SEC = 10
RECORD_FPS = 30


def _format_event_line(payload: dict) -> str:
    """이벤트 한 줄 표시 문자열 생성."""
    event_type = payload.get("event_type", "ALERT")
    msg = payload.get("message", "")
    ts = payload.get("timestamp") or payload.get("received_at") or datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    return f"[{ts}] {event_type} - {msg}"


class AlarmPopupWindow(QDialog):
    """알람 팝업: 실시간 영상 + 이벤트 리스트. 10초간 표시하며 10초 영상 자동 저장 후 DB에 기록."""

    def __init__(self, user_id: str, payload: dict, db: MySqlClient | None = None, parent=None):
        super().__init__(parent)
        self._user_id = user_id
        self._payload = payload
        self._db = db or MySqlClient(base_dir=_SCRIPT_DIR)
        self._event_list: list[dict] = [payload]
        self.setWindowTitle(f"알람 수신 - {user_id}")
        self.setMinimumSize(480, 400)
        self.resize(640, 520)
        self._init_ui()
        self._timer = QTimer(self)
        self._timer.timeout.connect(self._refresh_frame)
        self._timer.start(100)

        # 10초 후 자동 닫기
        self._close_timer = QTimer(self)
        self._close_timer.setSingleShot(True)
        self._close_timer.timeout.connect(self.accept)
        self._close_timer.start(POPUP_DURATION_SEC * 1000)

        # SAVE_MOV=true 일 때만 녹화 후 저장, false면 이벤트만 DB 저장
        save_mov = (read_env_values(base_dir=_SCRIPT_DIR).get("SAVE_MOV") or "true").strip().lower() == "true"
        if save_mov:
            self._start_auto_record()
        else:
            self._save_event_only()

    def _init_ui(self):
        layout = QVBoxLayout(self)
        # 영상 영역
        self.video_label = QLabel("영상 수신 대기 중...")
        self.video_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.video_label.setMinimumSize(320, 240)
        self.video_label.setStyleSheet("background-color: #000; color: #ccc;")
        layout.addWidget(self.video_label)

        # 발생 이벤트 목록 (영상 바로 밑)
        layout.addWidget(QLabel("발생한 이벤트:"))
        self.event_list_widget = QListWidget()
        self.event_list_widget.setMinimumHeight(100)
        self.event_list_widget.setStyleSheet("background-color: #242424; color: #e0e0e0; border: 1px solid #333;")
        layout.addWidget(self.event_list_widget, 1)

        # 초기 이벤트 1건 추가
        self._append_event_to_list(self._event_list[0])

    def _append_event_to_list(self, payload: dict):
        line = _format_event_line(payload)
        item = QListWidgetItem(line)
        self.event_list_widget.addItem(item)
        self.event_list_widget.scrollToBottom()

    def add_event(self, payload: dict):
        """동일 클라이언트에서 추가 이벤트(쓰러짐, 화재 등)가 들어오면 리스트에 Add."""
        self._event_list.append(payload)
        self._append_event_to_list(payload)

    def _refresh_frame(self):
        frame = get_latest_frame(self._user_id)
        if frame is None:
            return
        h, w, ch = frame.shape
        bytes_per_line = ch * w
        qimg = QImage(frame.data, w, h, bytes_per_line, QImage.Format.Format_RGB888)
        pix = QPixmap.fromImage(qimg).scaled(
            self.video_label.width(),
            self.video_label.height(),
            Qt.AspectRatioMode.KeepAspectRatio,
            Qt.TransformationMode.SmoothTransformation,
        )
        self.video_label.setPixmap(pix)

    def _save_event_only(self):
        """SAVE_MOV=false 시: 영상 없이 이벤트만 DB에 저장."""
        thread = threading.Thread(
            target=self._event_only_worker,
            args=(self._user_id, self._payload),
            daemon=True,
        )
        thread.start()

    def _event_only_worker(self, user_id: str, payload: dict):
        """녹화 없이 emergency_events에만 기록 (video_path 빈 문자열)."""
        try:
            raw_json = json.dumps(payload, ensure_ascii=False) if payload else None
            self._db.insert("emergency_events", {
                "user_id": user_id,
                "device_id": payload.get("device_id") or "",
                "event_type": payload.get("event_type") or "ALERT",
                "message": payload.get("message") or "",
                "video_path": "",
                "client_timestamp": payload.get("timestamp") or "",
                "raw_payload": raw_json,
            })
        except Exception as e:
            print(f"[AlarmPopup] DB 저장 실패: {e}")

    def _start_auto_record(self):
        """응급 발생 시 10초 영상 자동 저장 및 DB 기록 (SAVE_MOV=true일 때)."""
        payload = self._payload
        thread = threading.Thread(
            target=self._auto_record_worker,
            args=(self._user_id, payload),
            daemon=True,
        )
        thread.start()

    def _auto_record_worker(self, user_id: str, payload: dict):
        """백그라운드에서 10초 영상 수집, 파일 저장, DB 기록."""
        try:
            os.makedirs(MOV_DIR, exist_ok=True)
        except OSError as e:
            print(f"[AlarmPopup] 폴더 생성 실패: {e}")
            return

        frames = []
        interval = 1.0 / RECORD_FPS
        start = time.time()
        while (time.time() - start) < RECORD_DURATION_SEC:
            frame = get_latest_frame(user_id)
            if frame is not None:
                bgr = cv2.cvtColor(frame, cv2.COLOR_RGB2BGR)
                frames.append(bgr)
            time.sleep(interval)

        video_path = None
        if not frames:
            print("[AlarmPopup] SAVE_MOV=true지만 수신된 영상 프레임이 없어 파일을 저장하지 않습니다. (클라이언트가 실시간 영상 전송 중인지 확인)")
        if frames:
            ts = datetime.now().strftime("%Y%m%d_%H%M%S")
            filename = f"{user_id}_{ts}.mp4"
            filepath = os.path.join(MOV_DIR, filename)
            try:
                h, w = frames[0].shape[:2]
                fourcc = cv2.VideoWriter_fourcc(*"mp4v")
                writer = cv2.VideoWriter(filepath, fourcc, RECORD_FPS, (w, h))
                for f in frames:
                    writer.write(f)
                writer.release()
                video_path = filepath
            except Exception as e:
                print(f"[AlarmPopup] 영상 저장 실패: {e}")

        # DB에 응급 이벤트 저장
        try:
            raw_json = json.dumps(payload, ensure_ascii=False) if payload else None
            self._db.insert("emergency_events", {
                "user_id": user_id,
                "device_id": payload.get("device_id") or "",
                "event_type": payload.get("event_type") or "ALERT",
                "message": payload.get("message") or "",
                "video_path": video_path or "",
                "client_timestamp": payload.get("timestamp") or "",
                "raw_payload": raw_json,
            })
        except Exception as e:
            print(f"[AlarmPopup] DB 저장 실패: {e}")
