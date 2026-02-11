# -*- coding: utf-8 -*-
"""클라이언트 설정 파일 읽기/쓰기."""

import json
import os

CONFIG_FILENAME = "devices_config.json"
DEFAULT_CONFIG = {
    "rtsp_enable": False,
    "webcam_enable": False,
    "rtsp_url": "",
}


def get_config_path() -> str:
    """devices_config.json 경로 (client 폴더 기준)."""
    return os.path.join(os.path.dirname(os.path.abspath(__file__)), CONFIG_FILENAME)


def load_config() -> dict:
    """설정 로드. 없으면 기본값으로 새로 만들고 반환."""
    path = get_config_path()
    if not os.path.isfile(path):
        save_config(DEFAULT_CONFIG)
        return dict(DEFAULT_CONFIG)
    try:
        with open(path, "r", encoding="utf-8") as f:
            data = json.load(f)
    except Exception:
        data = dict(DEFAULT_CONFIG)
    # 기본 키 보장
    for key, default in DEFAULT_CONFIG.items():
        if key not in data:
            data[key] = default
    return data


def save_config(data: dict) -> None:
    """설정 저장."""
    path = get_config_path()
    out = {k: data.get(k, v) for k, v in DEFAULT_CONFIG.items()}
    with open(path, "w", encoding="utf-8") as f:
        json.dump(out, f, ensure_ascii=False, indent=2)
