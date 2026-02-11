import os
import time
import threading
import numpy as np
import cv2
from collections import deque

from fastapi import FastAPI, HTTPException, WebSocket, WebSocketDisconnect
from pydantic import BaseModel

from db_client import MySqlClient
from env_config import get_api_config

_SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))

app = FastAPI(title="AI Care Server API")
_db = MySqlClient(base_dir=_SCRIPT_DIR)
_server_started = False
_last_seen: dict[str, float] = {}
_last_seen_lock = threading.Lock()
_client_frames: dict[str, np.ndarray] = {}
_client_frames_lock = threading.Lock()
_alarm_queue = deque()
_alarm_lock = threading.Lock()


class RegisterRequest(BaseModel):
    user_id: str
    password: str
    name: str
    device_id: str
    gender: str = "M"
    blood_type: str | None = None
    address: str | None = None
    birth_date: str | None = None
    phone: str | None = None
    emergency_phone: str | None = None
    user_type: str = "NORMAL"
    monitor_target_id: str | None = None


class LoginRequest(BaseModel):
    user_id: str
    password: str


class AdminLoginRequest(BaseModel):
    user_id: str
    password: str

class KeepAliveRequest(BaseModel):
    user_id: str


class AlarmRequest(BaseModel):
    event_type: str | None = None
    message: str
    device_id: str | None = None
    user_id: str | None = None
    timestamp: str | None = None


@app.get("/health")
def health():
    return {"status": "ok"}


@app.post("/users/register")
def register_user(payload: RegisterRequest):
    exists = _db.fetch_one("SELECT user_id FROM users WHERE user_id=%s", (payload.user_id,))
    if exists:
        raise HTTPException(status_code=409, detail="user_id already exists")

    # index_no는 DB AUTO_INCREMENT로 생성. 클라이언트는 device_id만 전송.
    try:
        new_index_no = _db.insert(
            "users",
            {
                "device_id": payload.device_id,
                "user_id": payload.user_id,
                "password": payload.password,
                "name": payload.name,
                "gender": payload.gender,
                "blood_type": payload.blood_type,
                "address": payload.address,
                "birth_date": payload.birth_date,
                "phone": payload.phone,
                "emergency_phone": payload.emergency_phone,
                "user_type": payload.user_type,
                "monitor_target_id": payload.monitor_target_id,
            },
        )
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc))
    return {"status": "ok", "index_no": new_index_no}


@app.post("/auth/login")
def login(payload: LoginRequest):
    row = _db.fetch_one(
        "SELECT user_id FROM users WHERE user_id=%s AND password=%s",
        (payload.user_id, payload.password),
    )
    if not row:
        raise HTTPException(status_code=401, detail="invalid credentials")
    return {"status": "ok"}


@app.post("/auth/admin_login")
def admin_login(payload: AdminLoginRequest):
    """
    관리자 로그인용 엔드포인트.
    home_safe_admin.admin_users 테이블의 admin_id/admin_pw를 사용한다.
    (현재는 개발용으로 평문 비교)
    """
    row = _db.fetch_one(
        "SELECT admin_id FROM admin_users WHERE admin_id=%s AND admin_pw=%s AND is_active=1",
        (payload.user_id, payload.password),
    )
    if not row:
        raise HTTPException(status_code=401, detail="invalid credentials")
    return {"status": "ok"}


@app.post("/keepalive")
def keepalive(payload: KeepAliveRequest):
    now = time.time()
    with _last_seen_lock:
        _last_seen[payload.user_id] = now
    return {"status": "ok"}


@app.websocket("/ws/{user_id}")
async def stream_ws(websocket: WebSocket, user_id: str):
    await websocket.accept()
    try:
        while True:
            data = await websocket.receive_bytes()
            nparr = np.frombuffer(data, np.uint8)
            frame = cv2.imdecode(nparr, cv2.IMREAD_COLOR)
            if frame is None:
                continue
            rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
            with _client_frames_lock:
                _client_frames[user_id] = rgb
    except WebSocketDisconnect:
        with _client_frames_lock:
            _client_frames.pop(user_id, None)


@app.post("/alarm")
def alarm(payload: AlarmRequest):
    data = payload.dict()
    data["received_at"] = time.strftime("%Y-%m-%d %H:%M:%S")
    with _alarm_lock:
        _alarm_queue.append(data)
    return {"status": "ok"}


def get_keepalive_status(user_id: str, timeout_sec: int = 10) -> bool:
    now = time.time()
    with _last_seen_lock:
        last = _last_seen.get(user_id)
    if last is None:
        return False
    return (now - last) <= timeout_sec


def get_latest_frame(user_id: str):
    with _client_frames_lock:
        return _client_frames.get(user_id)


def pop_alarm():
    with _alarm_lock:
        if not _alarm_queue:
            return None
        return _alarm_queue.popleft()


def start_api_server():
    global _server_started
    if _server_started:
        return
    _server_started = True
    config = get_api_config(base_dir=_SCRIPT_DIR)
    host = config["host"]
    port = config["port"]

    def _run():
        import uvicorn

        uvicorn.run(app, host=host, port=port, log_level="warning")

    thread = threading.Thread(target=_run, daemon=True)
    thread.start()
