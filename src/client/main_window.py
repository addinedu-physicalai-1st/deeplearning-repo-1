import os
import sys

import cv2
import threading
import time
import json
import numpy as np
from PyQt6 import uic
from PyQt6.QtWidgets import QDialog, QVBoxLayout, QHBoxLayout, QTextEdit, QPushButton, QMessageBox
from PyQt6.QtCore import QTimer, Qt
from PyQt6.QtGui import QImage, QPixmap

_SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
_PROJECT_ROOT = os.path.dirname(_SCRIPT_DIR)
if _PROJECT_ROOT not in sys.path:
    sys.path.insert(0, _PROJECT_ROOT)

from env_config import read_env_values, update_env_file, resolve_path_from_base
import config as client_config
from api_client import keepalive, get_ws_url, send_alarm
from get_device_id import get_device_id


class TestMessageDialog(QDialog):
    """테스트 메시지 전송 팝업."""

    def __init__(self, user_id: str, event_text_callback=None, parent=None):
        super().__init__(parent)
        self.setWindowTitle("테스트 메시지 보내기")
        self.setMinimumSize(400, 300)
        self._event_text_callback = event_text_callback

        layout = QVBoxLayout(self)
        self._text = QTextEdit()
        self._text.setPlaceholderText("서버로 보낼 메시지를 입력하세요 (JSON).")
        sample = {
            "event_type": "ALERT",
            "message": "쓰러짐 발생",
            "device_id": get_device_id(),
            "user_id": user_id,
            "timestamp": time.strftime("%Y-%m-%d %H:%M:%S"),
        }
        self._text.setPlainText(json.dumps(sample, ensure_ascii=False, indent=2))
        layout.addWidget(self._text)

        btn_layout = QHBoxLayout()
        btn_layout.addStretch()
        btn_send = QPushButton("보내기")
        btn_close = QPushButton("닫기")
        btn_send.clicked.connect(self._on_send)
        btn_close.clicked.connect(self.accept)
        btn_layout.addWidget(btn_send)
        btn_layout.addWidget(btn_close)
        layout.addLayout(btn_layout)

    def _on_send(self):
        try:
            payload = json.loads(self._text.toPlainText().strip())
        except json.JSONDecodeError as e:
            QMessageBox.warning(self, "오류", f"JSON 형식이 올바르지 않습니다.\n{e}")
            return
        ok, msg = send_alarm(payload)
        if self._event_text_callback:
            if ok:
                self._event_text_callback("알람 전송 완료")
            else:
                self._event_text_callback(f"알람 전송 실패: {msg}")
        if ok:
            QMessageBox.information(self, "완료", "서버로 메시지가 전송되었습니다.")
        else:
            QMessageBox.warning(self, "실패", f"전송 실패: {msg}")


class MainWindow(QDialog):
    """클라이언트 메인 (탭 기반)."""

    def __init__(self, parent=None, user_id: str | None = None):
        super().__init__(parent)
        ui_path = os.path.join(_SCRIPT_DIR, "main_window.ui")
        uic.loadUi(ui_path, self)
        # 사용자 탭 레이아웃 비율 조정 (영상 화면 비중 확대)
        tab_layout = getattr(self, "tabUserLayout", None)
        if tab_layout is not None:
            # 0: video_title, 1: video_label, 2: eventHeaderLayout, 3: event_text
            tab_layout.setStretch(0, 0)
            tab_layout.setStretch(1, 5)  # 영상 영역 크게
            tab_layout.setStretch(2, 0)
            tab_layout.setStretch(3, 2)  # 이벤트 로그는 상대적으로 작게
        # 탭 위젯 / 탭 페이지 및 원래 인덱스/라벨을 캐시해둔다.
        # (removeTab / insertTab 방식으로 show/hide 제어)
        self._tab_widget = getattr(self, "main_tab", None)
        self._admin_tab = getattr(self, "tab_admin", None)
        self._vision_tab = getattr(self, "tab_vision", None)

        if self._tab_widget is not None and self._admin_tab is not None:
            idx = self._tab_widget.indexOf(self._admin_tab)
            self._admin_tab_index = idx if idx >= 0 else self._tab_widget.count()
            self._admin_tab_label = self._tab_widget.tabText(idx) if idx >= 0 else "관리자"
        else:
            self._admin_tab_index = 1
            self._admin_tab_label = "관리자"

        if self._tab_widget is not None and self._vision_tab is not None:
            idx = self._tab_widget.indexOf(self._vision_tab)
            self._vision_tab_index = idx if idx >= 0 else self._tab_widget.count()
            self._vision_tab_label = self._tab_widget.tabText(idx) if idx >= 0 else "비전 학습 모드"
        else:
            self._vision_tab_index = 2
            self._vision_tab_label = "비전 학습 모드"

        self._user_id = user_id or ""
        self._cap = None
        self._video_timer = QTimer(self)
        self._video_timer.timeout.connect(self._update_frame)
        self._keepalive_timer = QTimer(self)
        self._keepalive_timer.timeout.connect(self._send_keepalive)
        self._stream_thread = None
        self._stream_stop = threading.Event()
        self._latest_frame = None
        self._latest_lock = threading.Lock()
        self._fall_runner = None  # 통합 낙상 감지 (admin_ui.unified_fall_runner)
        self._ai_enabled = False
        self._frame_idx = 0
        self._last_alarm_ts = 0.0
        # 현재 모드(user/admin)를 미리 읽어서 저장
        env = read_env_values(base_dir=_SCRIPT_DIR)
        self._mode = (env.get("MODE") or "user").strip().lower()
        self._apply_mode()
        os.environ["ADMIN_UI_ENV_DIR"] = _SCRIPT_DIR  # 통합 모델이 client/.env 사용
        self._init_ai()
        # admin 모드에서는 사용자 탭의 카메라/RTSP를 열지 않음
        if self._mode != "admin":
            self._init_video()
        self._keepalive_timer.start(5000)
        self._start_streaming()
        self._init_debug()

    def _apply_mode(self):
        env = read_env_values(base_dir=_SCRIPT_DIR)
        mode = (env.get("MODE") or "user").strip().lower()
        if self._tab_widget is None:
            return
        
        print(f"mode: {mode}")

        # --- admin 모드: 관리자 탭만 보이도록 구성 ---
        if mode == "admin":
            # 사용자 탭 숨기기
            user_tab = getattr(self, "tab_user", None)
            if user_tab is not None:
                idx_user = self._tab_widget.indexOf(user_tab)
                if idx_user != -1:
                    self._tab_widget.removeTab(idx_user)

            # 비전 학습 모드 탭 숨기기
            if self._vision_tab is not None:
                idx_vis = self._tab_widget.indexOf(self._vision_tab)
                if idx_vis != -1:
                    self._tab_widget.removeTab(idx_vis)

            # 관리자 탭에 gui_ver4(admin_ui) 메인화면 임베드
            if self._admin_tab is not None:
                idx = self._tab_widget.indexOf(self._admin_tab)
                if idx == -1:
                    insert_idx = min(self._admin_tab_index, self._tab_widget.count())
                    self._tab_widget.insertTab(insert_idx, self._admin_tab, self._admin_tab_label)
                # 기존 내용 제거 후 AdminUiWidget 추가
                old_layout = self._admin_tab.layout()
                if old_layout:
                    while old_layout.count():
                        item = old_layout.takeAt(0)
                        if item.widget():
                            item.widget().deleteLater()
                else:
                    from PyQt6.QtWidgets import QVBoxLayout
                    self._admin_tab.setLayout(QVBoxLayout())
                os.environ["ADMIN_UI_ENV_DIR"] = _SCRIPT_DIR  # admin_ui DB는 클라이언트 .env 사용
                user_info = {"user_id": self._user_id, "name": self._user_id, "user_type": "관리자"}
                try:
                    try:
                        from client.admin_ui import AdminUiWidget
                    except ImportError:
                        from admin_ui import AdminUiWidget
                    self._admin_ui_widget = AdminUiWidget(user_info, parent=self._admin_tab)
                    self._admin_ui_widget.logout_requested.connect(self._on_admin_logout)
                    self._admin_tab.layout().addWidget(self._admin_ui_widget)
                except Exception as e:
                    from PyQt6.QtWidgets import QLabel
                    self._admin_tab.layout().addWidget(QLabel(f"관리자 UI 로드 실패: {e}"))

            if self._admin_tab is not None:
                self._tab_widget.setCurrentWidget(self._admin_tab)
            return

        # --- 기본(user) 모드: 관리자 / 비전 학습 탭 제거 ---
        if self._admin_tab is not None:
            idx = self._tab_widget.indexOf(self._admin_tab)
            if idx != -1:
                self._tab_widget.removeTab(idx)

        if self._vision_tab is not None:
            idx = self._tab_widget.indexOf(self._vision_tab)
            if idx != -1:
                self._tab_widget.removeTab(idx)

    def _init_video(self):
        """devices_config.json 기준: rtsp_enable+rtsp_url → RTSP, webcam_enable → 웹캠. 둘 다 AI 판독 적용."""
        cfg = client_config.load_config()
        rtsp_enable = cfg.get("rtsp_enable", False)
        webcam_enable = cfg.get("webcam_enable", False)
        rtsp_url = (cfg.get("rtsp_url") or "").strip()

        # RTSP: rtsp_player3 참고, CAP_FFMPEG로 RTSP 안정화
        if rtsp_enable and rtsp_url:
            self._cap = cv2.VideoCapture(rtsp_url, cv2.CAP_FFMPEG)
        elif webcam_enable:
            self._cap = cv2.VideoCapture(0)
        else:
            self._cap = None

        if self._cap is None or not self._cap.isOpened():
            if hasattr(self, "video_label"):
                src = "RTSP" if (rtsp_enable and rtsp_url) else "웹캠"
                self.video_label.setText(f"{src} 영상 장치를 사용할 수 없습니다.")
            return
        src = "RTSP" if (rtsp_enable and rtsp_url) else "웹캠"
        if hasattr(self, "event_text"):
            self.event_text.append(f"[VIDEO] {src} 연결됨")
        self._video_timer.start(33)

    def _update_frame(self):
        if self._cap is None:
            return
        ret, frame = self._cap.read()
        if not ret or frame is None:
            return
        annotated = self._process_ai(frame)
        with self._latest_lock:
            self._latest_frame = annotated.copy()
        h, w, ch = frame.shape
        bytes_per_line = ch * w
        rgb = cv2.cvtColor(annotated, cv2.COLOR_BGR2RGB)
        qimg = QImage(rgb.data, w, h, bytes_per_line, QImage.Format.Format_RGB888)
        if hasattr(self, "video_label"):
            pix = QPixmap.fromImage(qimg).scaled(
                self.video_label.width(),
                self.video_label.height(),
                Qt.AspectRatioMode.KeepAspectRatio,
                Qt.TransformationMode.SmoothTransformation,
            )
            self.video_label.setPixmap(pix)

    def _init_ai(self):
        """통합 낙상 감지 러너 초기화 (.env USE_MODEL 기반)."""
        try:
            try:
                from client.admin_ui.unified_fall_runner import UnifiedFallRunner
            except ImportError:
                from admin_ui.unified_fall_runner import UnifiedFallRunner
            self._fall_runner = UnifiedFallRunner(env_dir=_SCRIPT_DIR)
            self._ai_enabled = self._fall_runner.yolo_model is not None
        except Exception as e:
            self._fall_runner = None
            self._ai_enabled = False
            if hasattr(self, "event_text"):
                self.event_text.append(f"[AI] 통합 모델 로드 실패: {e}")
            return
        if hasattr(self, "event_text"):
            if self._ai_enabled:
                self.event_text.append(f"[AI] 통합 낙상 감지 로드 ({getattr(self._fall_runner, 'model_name', '?')})")
            else:
                self.event_text.append("[AI] YOLO Pose 모델 없음 - AI 비활성")

    def _process_ai(self, frame):
        """통합 낙상 감지: 스켈레톤·상태 오버레이 후 반환, 낙상 시 서버 전송."""
        if not self._ai_enabled or self._fall_runner is None:
            return frame
        try:
            annotated, state_str, is_fallen = self._fall_runner.process(frame)
            if is_fallen:
                self._send_fall_event()
            return annotated
        except Exception:
            return frame

    def _send_fall_event(self):
        now = time.time()
        if now - self._last_alarm_ts < 10:
            return
        # 클라이언트 이벤트 로그에 쓰러짐 감지 내역 추가
        if hasattr(self, "event_text"):
            ts = time.strftime("%Y-%m-%d %H:%M:%S")
            self.event_text.append(f"[ALERT] {ts} 쓰러짐 감지 되었다")
        # 관리자 모드(또는 관리자 계정)에서는 서버로 이벤트를 보내지 않음
        from env_config import read_env_values
        env = read_env_values(base_dir=_SCRIPT_DIR)
        mode = (env.get("MODE") or "user").strip().lower()
        if mode == "admin" or (self._user_id and self._user_id.lower() == "admin"):
            # 개발/테스트용으로만 콘솔에 남기고 서버 알람 전송은 차단
            print("[INFO] 관리자 모드에서 발생한 이벤트는 서버로 전송하지 않습니다.")
            return
        self._last_alarm_ts = now
        payload = {
            "event_type": "ALERT",
            "message": "쓰러짐 발생",
            "device_id": get_device_id(),
            "user_id": self._user_id,
            "timestamp": time.strftime("%Y-%m-%d %H:%M:%S"),
        }
        ok, msg = send_alarm(payload)
        if hasattr(self, "event_text"):
            self.event_text.append(f"[서버] 쓰러짐 이벤트 전송 {'완료' if ok else f'실패: {msg}'}")

    def _on_admin_logout(self):
        """관리자 탭에서 로그아웃 요청 시 사용자 탭으로 전환."""
        if self._tab_widget and hasattr(self, "tab_user"):
            self._tab_widget.setCurrentWidget(self.tab_user)
        if hasattr(self, "_admin_ui_widget") and self._admin_ui_widget:
            self._admin_ui_widget.stop_monitoring()

    def _init_debug(self):
        if not hasattr(self, "btn_test_message"):
            return

        def _open_test_dialog():
            callback = None
            if hasattr(self, "event_text"):
                callback = lambda m: self.event_text.append(m)
            dlg = TestMessageDialog(user_id=self._user_id, event_text_callback=callback, parent=self)
            dlg.exec()

        self.btn_test_message.clicked.connect(_open_test_dialog)

    def _start_streaming(self):
        if not self._user_id:
            return
        self._stream_stop.clear()
        self._stream_thread = threading.Thread(target=self._stream_loop, daemon=True)
        self._stream_thread.start()

    def _stream_loop(self):
        try:
            import asyncio
            import websockets
        except Exception:
            return

        async def _send():
            uri = get_ws_url(self._user_id)
            try:
                async with websockets.connect(uri, max_size=2**20) as ws:
                    while not self._stream_stop.is_set():
                        frame = None
                        with self._latest_lock:
                            if self._latest_frame is not None:
                                frame = self._latest_frame.copy()
                        if frame is None:
                            await asyncio.sleep(0.03)
                            continue
                        ok, buffer = cv2.imencode(".jpg", frame, [int(cv2.IMWRITE_JPEG_QUALITY), 80])
                        if ok:
                            await ws.send(buffer.tobytes())
                        await asyncio.sleep(0.03)
            except Exception:
                return

        asyncio.run(_send())

    def _send_keepalive(self):
        if not self._user_id:
            return
        keepalive(self._user_id)

    def closeEvent(self, event):
        # 관리자 모드로 열렸다가 종료 시 MODE를 user로 되돌림
        env = read_env_values(base_dir=_SCRIPT_DIR)
        mode = (env.get("MODE") or "user").strip().lower()
        if mode == "admin":
            update_env_file(base_dir=_SCRIPT_DIR, updates={"MODE": "user"})
        self._stream_stop.set()
        if self._cap is not None:
            self._cap.release()
            self._cap = None
        super().closeEvent(event)
