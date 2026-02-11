import os
from dotenv import load_dotenv

# 모델 경로는 base_dir 기준 상대경로 (예: client/ 또는 프로젝트 루트)
DEFAULT_ENV = {
    "DB_HOST": "127.0.0.1",
    "DB_PORT": "3306",
    "DB_USER": "root",
    "DB_PASSWORD": "root",
    "DB_NAME": "home_safe",
    "API_HOST": "127.0.0.1",
    "API_PORT": "8000",
    "MODE": "user",
    "SAVE_MOV": "true",  # 서버: 알람 팝업 시 영상 녹화 저장 여부 (true/false)
    "USE_MODEL": "RandomForest",  # 낙상 감지: RandomForest | ST-GCN-Original | ST-GCN-Fine-tuned
    "SHOWINFO": "true",  # 사용자 탭 영상 오버레이: Frame, YOLO Pose ON, Detection Acc 표시 (true/false)
    "DEBUG_UI": "true",  # true: 사용자 탭 오버레이를 관리자 탭과 동일하게 (FN Detection Acc, 진행바, 예측 박스)
}


def resolve_path_from_base(path_value: str, base_dir: str) -> str:
    """env에 저장된 경로를 base_dir 기준 절대경로로 변환.

    - 비어 있으면 '' 반환.
    - 이미 절대경로면 그대로 반환.
    - 상대경로면 base_dir과 join 후 abspath 반환.
    (monitoring_page.py의 base_dir 활용 방식과 동일)
    """
    if not path_value or not isinstance(path_value, str):
        return ""
    path_value = path_value.strip()
    if not path_value:
        return ""
    if os.path.isabs(path_value):
        return path_value
    base = os.path.abspath(base_dir)
    return os.path.abspath(os.path.join(base, path_value))


def _resolve_base_dir(base_dir: str | None) -> str:
    if base_dir:
        return os.path.abspath(base_dir)
    return os.path.dirname(os.path.abspath(__file__))


def get_env_path(base_dir: str | None = None) -> str:
    return os.path.join(_resolve_base_dir(base_dir), ".env")


def _read_env_file(env_path: str) -> dict:
    if not os.path.isfile(env_path):
        return {}
    result = {}
    with open(env_path, "r", encoding="utf-8") as f:
        for raw in f:
            line = raw.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue
            key, value = line.split("=", 1)
            value = value.strip()
            if " #" in value:
                value = value.split(" #", 1)[0].strip()
            result[key.strip()] = value
    return result


def read_env_values(base_dir: str | None = None) -> dict:
    env_path = get_env_path(base_dir)
    return _read_env_file(env_path)


def update_env_file(base_dir: str | None, updates: dict) -> str:
    env_path = get_env_path(base_dir)
    existing = _read_env_file(env_path)
    existing.update({k: str(v) for k, v in updates.items()})
    with open(env_path, "w", encoding="utf-8") as f:
        for key, value in existing.items():
            f.write(f"{key}={value}\n")
    return env_path


def ensure_env_file(base_dir: str | None = None) -> tuple[bool, bool, str]:
    """Ensure .env exists and has required keys.

    Returns (created, updated, env_path).
    """
    env_path = get_env_path(base_dir)
    created = False
    updated = False
    if not os.path.isfile(env_path):
        created = True
        with open(env_path, "w", encoding="utf-8") as f:
            for key, value in DEFAULT_ENV.items():
                f.write(f"{key}={value}\n")
        return created, updated, env_path

    existing = _read_env_file(env_path)
    missing = [key for key in DEFAULT_ENV.keys() if key not in existing]
    # 클라이언트(.env)에는 SAVE_MOV를 자동으로 채우지 않는다 (서버 전용 설정)
    base_dir_resolved = _resolve_base_dir(base_dir)
    if os.path.basename(base_dir_resolved) == "client":
        missing = [key for key in missing if key != "SAVE_MOV"]
    if missing:
        updated = True
        with open(env_path, "a", encoding="utf-8") as f:
            f.write("\n# Auto-filled defaults\n")
            for key in missing:
                f.write(f"{key}={DEFAULT_ENV[key]}\n")
    return created, updated, env_path


def load_env(base_dir: str | None = None) -> str:
    env_path = get_env_path(base_dir)
    load_dotenv(env_path, override=False)
    return env_path


def get_db_config(base_dir: str | None = None) -> dict:
    if base_dir:
        load_env(base_dir)
    return {
        "host": os.environ.get("DB_HOST", DEFAULT_ENV["DB_HOST"]),
        "port": int(os.environ.get("DB_PORT", DEFAULT_ENV["DB_PORT"])),
        "user": os.environ.get("DB_USER", DEFAULT_ENV["DB_USER"]),
        "password": os.environ.get("DB_PASSWORD", DEFAULT_ENV["DB_PASSWORD"]),
        "name": os.environ.get("DB_NAME", DEFAULT_ENV["DB_NAME"]),
    }


def get_api_config(base_dir: str | None = None) -> dict:
    if base_dir:
        load_env(base_dir)
    return {
        "host": os.environ.get("API_HOST", DEFAULT_ENV["API_HOST"]),
        "port": int(os.environ.get("API_PORT", DEFAULT_ENV["API_PORT"])),
    }


def test_db_connection(config: dict, connect_timeout: int = 3) -> tuple[bool, str]:
    try:
        import pymysql
    except Exception as exc:
        return False, f"PyMySQL import 실패: {exc}"

    try:
        conn = pymysql.connect(
            host=config["host"],
            port=config["port"],
            user=config["user"],
            password=config["password"],
            database=config["name"],
            connect_timeout=connect_timeout,
            charset="utf8mb4",
        )
        conn.close()
        return True, "ok"
    except Exception as exc:
        return False, str(exc)


def database_exists(config: dict, connect_timeout: int = 3) -> tuple[bool, str]:
    """DB_NAME이 존재하는지 확인. (True, "ok") 또는 (False, error_msg)."""
    try:
        import pymysql
    except Exception as exc:
        return False, f"PyMySQL import 실패: {exc}"

    try:
        conn = pymysql.connect(
            host=config["host"],
            port=config["port"],
            user=config["user"],
            password=config["password"],
            database="information_schema",
            connect_timeout=connect_timeout,
            charset="utf8mb4",
        )
        try:
            with conn.cursor() as cur:
                cur.execute(
                    "SELECT SCHEMA_NAME FROM information_schema.SCHEMATA WHERE SCHEMA_NAME = %s",
                    (config["name"],),
                )
                exists = cur.fetchone() is not None
                return (True, "ok") if exists else (False, f"데이터베이스 '{config['name']}'가 존재하지 않습니다.")
        finally:
            conn.close()
    except Exception as exc:
        return False, str(exc)


def run_setup_sql_file(sql_path: str, config: dict, connect_timeout: int = 30) -> tuple[bool, str]:
    """SQL 파일 실행 (root 등 DB 권한 있는 계정 필요). (True, "ok") 또는 (False, error_msg)."""
    import subprocess
    import shutil

    if not os.path.isfile(sql_path):
        return False, f"SQL 파일 없음: {sql_path}"

    # mysql 실행 파일 경로 (GUI 앱에서는 PATH에 없을 수 있음)
    mysql_exe = shutil.which("mysql") or "/usr/bin/mysql"

    # 1) mysql 클라이언트로 실행 (표준 방식, 주석/따옴표 등 파싱 이슈 없음)
    cmd = [
        mysql_exe,
        "-h", config["host"],
        "-P", str(config["port"]),
        "-u", config["user"],
        f"--password={config['password']}",
        "--default-character-set=utf8mb4",
        "--connect-timeout", str(connect_timeout),
    ]
    try:
        with open(sql_path, "r", encoding="utf-8") as f:
            result = subprocess.run(
                cmd,
                stdin=f,
                capture_output=True,
                text=True,
                timeout=connect_timeout + 10,
            )
        if result.returncode != 0:
            err = (result.stderr or result.stdout or "알 수 없는 오류").strip()
            return False, err
        return True, "ok"
    except FileNotFoundError:
        pass  # mysql 미설치 시 pymysql 폴백
    except subprocess.TimeoutExpired:
        return False, "SQL 실행 시간 초과"
    except Exception as exc:
        return False, str(exc)

    # 2) mysql 미설치 시 pymysql로 직접 실행
    try:
        import pymysql
        conn = pymysql.connect(
            host=config["host"],
            port=config["port"],
            user=config["user"],
            password=config["password"],
            database="mysql",
            connect_timeout=connect_timeout,
            charset="utf8mb4",
        )
        try:
            with open(sql_path, "r", encoding="utf-8") as f:
                sql_content = f.read()

            # 주석(--로 시작하는 줄) 제거 후 문장별 실행
            lines = []
            for line in sql_content.splitlines():
                s = line.strip()
                if s and not s.startswith("--"):
                    lines.append(line)
            clean_sql = "\n".join(lines)
            statements = [s.strip() for s in clean_sql.split(";") if s.strip()]

            with conn.cursor() as cur:
                for stmt in statements:
                    if stmt:
                        cur.execute(stmt)
            conn.commit()
            return True, "ok"
        finally:
            conn.close()
    except ImportError:
        return False, "PyMySQL import 실패. mysql-client 설치 또는 PyMySQL 설치 후 다시 시도하세요."
    except Exception as exc:
        return False, str(exc)
