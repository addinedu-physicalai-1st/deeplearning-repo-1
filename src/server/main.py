"""
AI Care Server - 메인 실행 파일

실행 방법 (프로젝트 루트에서):
    python -m server.main
또는 server 폴더에서:
    cd server && python main.py
"""
import os
import sys
import fcntl
from PyQt6.QtWidgets import QApplication, QMessageBox
from PyQt6.QtGui import QFont

# server 폴더를 path에 추가 (init_window 등 import용)
_SERVER_DIR = os.path.dirname(os.path.abspath(__file__))
_PROJECT_ROOT = os.path.dirname(_SERVER_DIR)
if _SERVER_DIR not in sys.path:
    sys.path.insert(0, _SERVER_DIR)
if _PROJECT_ROOT not in sys.path:
    sys.path.insert(0, _PROJECT_ROOT)

from init_window import InitWindow
from env_config import ensure_env_file, load_env

_server_lock_file = None


def _ensure_single_instance():
    """서버 프로그램 단일 인스턴스 보장."""
    global _server_lock_file
    lock_path = "/tmp/ai_care_server.lock"
    _server_lock_file = open(lock_path, "w")
    try:
        fcntl.flock(_server_lock_file.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
    except BlockingIOError:
        QMessageBox.critical(None, "AI Care Server", "프로세스가 이미 실행 중입니다.")
        sys.exit(1)


def main():
    ensure_env_file(base_dir=_SERVER_DIR)
    load_env(base_dir=_SERVER_DIR)
    app = QApplication(sys.argv)
    app.setFont(QFont("맑은 고딕", 10))
    app.setApplicationName("AI Care Server")
    app.setApplicationDisplayName("AI Care - 서버")

    _ensure_single_instance()

    win = InitWindow()
    win.show()
    sys.exit(app.exec())


if __name__ == "__main__":
    os.environ["QT_IM_MODULE"] = "ibus"  # 입력기 모드 설정 (KDE는 보통 fcitx, 안되면 ibus 시도)
    main()
