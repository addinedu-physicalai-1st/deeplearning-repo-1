import uuid
import hashlib


def get_device_id() -> str:
    """MAC 주소 기반 SHA-256 디바이스 ID 반환."""
    mac_addr = hex(uuid.getnode())
    return hashlib.sha256(mac_addr.encode()).hexdigest()


if __name__ == "__main__":
    device_id = get_device_id()
    print(f"Hashed for DB: {device_id}")