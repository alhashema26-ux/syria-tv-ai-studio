"""
Database Module - PostgreSQL connection and operations
"""
import os
import json
import psycopg2
import psycopg2.extras
from datetime import datetime


def get_connection():
    """يرجع connection للـ PostgreSQL."""
    return psycopg2.connect(os.environ["DATABASE_URL"])


def init_db():
    """ينشئ الجداول إذا ما كانت موجودة."""
    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute("""
                CREATE TABLE IF NOT EXISTS reports (
                    id SERIAL PRIMARY KEY,
                    job_id VARCHAR(12) UNIQUE NOT NULL,
                    status VARCHAR(20) DEFAULT 'running',
                    transcript TEXT,
                    content_type VARCHAR(100),
                    program_name VARCHAR(100),
                    result_data JSONB,
                    cost FLOAT DEFAULT 0.0,
                    error TEXT,
                    created_at TIMESTAMP DEFAULT NOW(),
                    updated_at TIMESTAMP DEFAULT NOW()
                );
            """)
        conn.commit()
    print("[DB] Tables initialized ✅")


def save_job(job_id: str, transcript: str, content_type: str = None, program_name: str = None):
    """يحفظ job جديد بحالة running."""
    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute("""
                INSERT INTO reports (job_id, status, transcript, content_type, program_name)
                VALUES (%s, 'running', %s, %s, %s)
                ON CONFLICT (job_id) DO NOTHING;
            """, (job_id, transcript, content_type, program_name))
        conn.commit()


def update_job(job_id: str, status: str, result_data: dict = None, cost: float = 0.0, error: str = None):
    """يحدّث حالة الـ job والنتائج."""
    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute("""
                UPDATE reports
                SET status = %s,
                    result_data = %s,
                    cost = %s,
                    error = %s,
                    updated_at = NOW()
                WHERE job_id = %s;
            """, (status, json.dumps(result_data, ensure_ascii=False) if result_data else None, cost, error, job_id))
        conn.commit()


def get_job(job_id: str) -> dict | None:
    """يجلب job بالـ job_id."""
    with get_connection() as conn:
        with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
            cur.execute("SELECT * FROM reports WHERE job_id = %s;", (job_id,))
            row = cur.fetchone()
            if not row:
                return None
            result = dict(row)
            if result.get("result_data") and isinstance(result["result_data"], str):
                result["result_data"] = json.loads(result["result_data"])
            return result


def list_jobs(limit: int = 50) -> list:
    """يجلب آخر التقارير."""
    with get_connection() as conn:
        with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
            cur.execute("""
                SELECT job_id, status, content_type, program_name, cost, created_at
                FROM reports
                ORDER BY created_at DESC
                LIMIT %s;
            """, (limit,))
            return [dict(row) for row in cur.fetchall()]
