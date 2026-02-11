"""
AI Care Client - 메인 실행 파일

실행 방법 (프로젝트 루트에서):
    python -m client.main
또는 client 폴더에서:
    cd client && python main.py
"""
import os
import sys
import fcntl
from PyQt6.QtWidgets import QApplication, QMessageBox
from PyQt6.QtGui import QFont

# client 폴더 기준으로 프로젝트 루트를 path에 추가 (rtsp_test, webcam_test import용)
_CLIENT_DIR = os.path.dirname(os.path.abspath(__file__))
_PROJECT_ROOT = os.path.dirname(_CLIENT_DIR)
if _PROJECT_ROOT not in sys.path:
    sys.path.insert(0, _PROJECT_ROOT)

from init_window import InitWindow
from env_config import ensure_env_file, load_env

_client_lock_file = None


def _ensure_single_instance():
    """클라이언트 프로그램 단일 인스턴스 보장."""
    global _client_lock_file
    lock_path = "/tmp/ai_care_client.lock"
    _client_lock_file = open(lock_path, "w")
    try:
        fcntl.flock(_client_lock_file.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
    except BlockingIOError:
        QMessageBox.critical(None, "AI Care Client", "프로세스가 이미 실행 중입니다.")
        sys.exit(1)


def main():
    ensure_env_file(base_dir=_CLIENT_DIR)
    load_env(base_dir=_CLIENT_DIR)
    app = QApplication(sys.argv)
    app.setFont(QFont("맑은 고딕", 10))
    app.setApplicationName("AI Care Client")
    app.setApplicationDisplayName("AI Care - 클라이언트")

    _ensure_single_instance()

    win = InitWindow()
    win.show()
    sys.exit(app.exec())


if __name__ == "__main__":
    os.environ["QT_IM_MODULE"] = "ibus"  # 입력기 모드 설정 (KDE는 보통 fcitx, 안되면 ibus 시도)
    main()

#클라이언트 