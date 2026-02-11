import os
import sys
import requests

_SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
_PROJECT_ROOT = os.path.dirname(_SCRIPT_DIR)
if _PROJECT_ROOT not in sys.path:
    sys.path.insert(0, _PROJECT_ROOT)

from env_config import get_api_config


def _base_url() -> str:
    config = get_api_config(base_dir=_SCRIPT_DIR)
    return f"http://{config['host']}:{config['port']}"


def get_ws_url(user_id: str) -> str:
    config = get_api_config(base_dir=_SCRIPT_DIR)
    return f"ws://{config['host']}:{config['port']}/ws/{user_id}"


def register_user(payload: dict) -> tuple[bool, str]:
    """사용자 등록 API 호출.

    실패 시 서버에서 내려온 상세 에러(JSON/텍스트)는 내부 로그에만 남기고,
    호출 측에는 사용자용 일반 메시지를 돌려준다.
    """
    try:
        resp = requests.post(f"{_base_url()}/users/register", json=payload, timeout=5)
    except Exception as exc:
        return False, f"요청 실패: {exc}"
    if resp.status_code == 200:
        return True, "ok"

    # 서버 detail은 콘솔 로그로만 남기고 UI에는 노출하지 않음
    try:
        data = resp.json()
        detail = data.get("detail")
        if detail:
            print(f"[register_user] 실패 detail: {detail}")
    except Exception:
        if resp.text:
            print(f"[register_user] 실패 raw: {resp.text}")
    return False, "등록이 실패하였습니다."


def login_user(user_id: str, password: str) -> tuple[bool, str]:
    try:
        resp = requests.post(
            f"{_base_url()}/auth/login",
            json={"user_id": user_id, "password": password},
            timeout=5,
        )
    except Exception as exc:
        return False, f"요청 실패: {exc}"
    if resp.status_code == 200:
        return True, "ok"
    if resp.status_code == 401:
        return False, "아이디 또는 비밀번호가 올바르지 않습니다."
    try:
        data = resp.json()
        detail = data.get("detail")
        if detail:
            return False, str(detail)
    except Exception:
        pass
    return False, "로그인에 실패했습니다."


def login_admin(user_id: str, password: str) -> tuple[bool, str]:
    """관리자 전용 로그인 API 호출 (/auth/admin_login)."""
    try:
        resp = requests.post(
            f"{_base_url()}/auth/admin_login",
            json={"user_id": user_id, "password": password},
            timeout=5,
        )
    except Exception as exc:
        return False, f"요청 실패: {exc}"
    if resp.status_code == 200:
        return True, "ok"
    if resp.status_code == 401:
        return False, "관리자 ID 또는 비밀번호가 올바르지 않습니다."
    try:
        data = resp.json()
        detail = data.get("detail")
        if detail:
            return False, str(detail)
    except Exception:
        pass
    return False, "관리자 로그인에 실패했습니다."

def health_check() -> tuple[bool, str]:
    try:
        resp = requests.get(f"{_base_url()}/health", timeout=3)
    except Exception as exc:
        return False, f"요청 실패: {exc}"
    if resp.status_code == 200:
        return True, "ok"
    return False, resp.text


def keepalive(user_id: str) -> tuple[bool, str]:
    try:
        resp = requests.post(
            f"{_base_url()}/keepalive",
            json={"user_id": user_id},
            timeout=3,
        )
    except Exception as exc:
        return False, f"요청 실패: {exc}"
    if resp.status_code == 200:
        return True, "ok"
    return False, resp.text


def send_alarm(payload: dict) -> tuple[bool, str]:
    try:
        resp = requests.post(f"{_base_url()}/alarm", json=payload, timeout=5)
    except Exception as exc:
        return False, f"요청 실패: {exc}"
    if resp.status_code == 200:
        return True, "ok"
    try:
        data = resp.json()
        detail = data.get("detail")
        if detail:
            return False, str(detail)
    except Exception:
        pass
    return False, "알람 전송에 실패했습니다."
