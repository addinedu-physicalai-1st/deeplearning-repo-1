import os
import pymysql
from pymysql.cursors import DictCursor

from env_config import get_db_config


class MySqlClient:
    """간단한 CRUD 유틸 클래스."""

    def __init__(self, config: dict | None = None, base_dir: str | None = None):
        if base_dir is None:
            base_dir = os.path.dirname(os.path.abspath(__file__))
        self._config = config or get_db_config(base_dir=base_dir)

    def _connect(self):
        return pymysql.connect(
            host=self._config["host"],
            port=self._config["port"],
            user=self._config["user"],
            password=self._config["password"],
            database=self._config["name"],
            charset="utf8mb4",
            cursorclass=DictCursor,
            autocommit=False,
        )

    def execute(self, query: str, params: tuple | dict | None = None) -> int:
        """INSERT/UPDATE/DELETE 등에 사용. 영향받은 row 수 반환."""
        with self._connect() as conn:
            with conn.cursor() as cur:
                cur.execute(query, params)
            conn.commit()
            return conn.affected_rows()

    def fetch_one(self, query: str, params: tuple | dict | None = None) -> dict | None:
        """SELECT 1건 조회."""
        with self._connect() as conn:
            with conn.cursor() as cur:
                cur.execute(query, params)
                return cur.fetchone()

    def fetch_all(self, query: str, params: tuple | dict | None = None) -> list[dict]:
        """SELECT 다건 조회."""
        with self._connect() as conn:
            with conn.cursor() as cur:
                cur.execute(query, params)
                return cur.fetchall()

    def insert(self, table: str, data: dict) -> int:
        """딕셔너리를 INSERT 하고 lastrowid 반환."""
        keys = ", ".join(f"`{k}`" for k in data.keys())
        placeholders = ", ".join(["%s"] * len(data))
        sql = f"INSERT INTO `{table}` ({keys}) VALUES ({placeholders})"
        values = tuple(data.values())
        with self._connect() as conn:
            with conn.cursor() as cur:
                cur.execute(sql, values)
                conn.commit()
                return cur.lastrowid

    def update(self, table: str, data: dict, where: str, params: tuple | dict) -> int:
        """조건에 맞는 데이터 업데이트."""
        set_clause = ", ".join([f"`{k}`=%s" for k in data.keys()])
        sql = f"UPDATE `{table}` SET {set_clause} WHERE {where}"
        values = tuple(data.values())
        with self._connect() as conn:
            with conn.cursor() as cur:
                cur.execute(sql, values + (params if isinstance(params, tuple) else tuple(params.values())))
            conn.commit()
            return conn.affected_rows()

    def delete(self, table: str, where: str, params: tuple | dict) -> int:
        """조건에 맞는 데이터 삭제."""
        sql = f"DELETE FROM `{table}` WHERE {where}"
        return self.execute(sql, params)

    def transaction(self, queries: list[tuple[str, tuple | dict | None]]):
        """여러 쿼리를 하나의 트랜잭션으로 실행."""
        with self._connect() as conn:
            with conn.cursor() as cur:
                for query, params in queries:
                    cur.execute(query, params)
            conn.commit()
