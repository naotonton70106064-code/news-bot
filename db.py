"""ローカル PostgreSQL への接続ヘルパー。接続情報は .env (DB_*) から読む。"""
import os

import psycopg
from dotenv import load_dotenv

load_dotenv()

REQUIRED_KEYS = ("DB_HOST", "DB_PORT", "DB_USER", "DB_PASSWORD", "DB_NAME")


def get_connection(**kwargs):
    """.env の DB_* を使って psycopg 接続を返す。不足があれば明示的に落とす。"""
    missing = [k for k in REQUIRED_KEYS if not os.getenv(k)]
    if missing:
        raise RuntimeError(f".env に {', '.join(missing)} が設定されていません")
    return psycopg.connect(
        host=os.environ["DB_HOST"],
        port=int(os.environ["DB_PORT"]),
        user=os.environ["DB_USER"],
        password=os.environ["DB_PASSWORD"],
        dbname=os.environ["DB_NAME"],
        **kwargs,
    )


if __name__ == "__main__":
    with get_connection() as conn:
        print(conn.execute("SELECT version()").fetchone()[0])
