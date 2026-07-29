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


def get_stats() -> dict:
    """إحصائيات عامة للـ Dashboard."""
    with get_connection() as conn:
        with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
            cur.execute("""
                SELECT
                    COUNT(*) as total_reports,
                    COUNT(*) FILTER (WHERE status = 'done') as completed,
                    COUNT(*) FILTER (WHERE status = 'error') as failed,
                    COUNT(*) FILTER (WHERE status = 'running') as running,
                    COALESCE(SUM(cost), 0) as total_cost,
                    COALESCE(AVG(cost) FILTER (WHERE status = 'done'), 0) as avg_cost,
                    COALESCE(AVG((result_data->'evaluation'->>'overall_score')::float) 
                        FILTER (WHERE result_data->'evaluation' IS NOT NULL), 0) as avg_quality
                FROM reports;
            """)
            stats = dict(cur.fetchone())

            # أكثر البرامج استخداماً
            cur.execute("""
                SELECT program_name, COUNT(*) as count
                FROM reports
                WHERE program_name IS NOT NULL AND status = 'done'
                GROUP BY program_name
                ORDER BY count DESC
                LIMIT 5;
            """)
            stats['top_programs'] = [dict(r) for r in cur.fetchall()]

            # أكثر أنواع المحتوى
            cur.execute("""
                SELECT content_type, COUNT(*) as count
                FROM reports
                WHERE content_type IS NOT NULL AND status = 'done'
                GROUP BY content_type
                ORDER BY count DESC
                LIMIT 5;
            """)
            stats['top_content_types'] = [dict(r) for r in cur.fetchall()]

            # التقارير اليومية آخر 7 أيام
            cur.execute("""
                SELECT
                    DATE(created_at) as date,
                    COUNT(*) as count,
                    COALESCE(SUM(cost), 0) as daily_cost
                FROM reports
                WHERE created_at >= NOW() - INTERVAL '7 days'
                    AND status = 'done'
                GROUP BY DATE(created_at)
                ORDER BY date;
            """)
            stats['daily_reports'] = [dict(r) for r in cur.fetchall()]

            return stats


def get_recent_reports(limit: int = 20) -> list:
    """آخر التقارير مع تفاصيلها."""
    with get_connection() as conn:
        with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
            cur.execute("""
                SELECT
                    job_id,
                    status,
                    content_type,
                    program_name,
                    cost,
                    created_at,
                    LEFT(transcript, 100) as transcript_preview,
                    (result_data->'evaluation'->>'overall_score')::float as quality_score,
                    result_data->'titles'->'titles'->0->>'text' as recommended_title
                FROM reports
                WHERE status = 'done'
                ORDER BY created_at DESC
                LIMIT %s;
            """, (limit,))
            return [dict(r) for r in cur.fetchall()]
