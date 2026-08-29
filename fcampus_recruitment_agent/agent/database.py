# -*- coding: utf-8 -*-
"""
SQLite 数据库模块：存储筛选记录、操作日志
轻量级，无需额外安装数据库服务
"""
import os
import sqlite3
import json
from datetime import datetime

DB_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "data", "app.db")


def get_conn():
    """获取数据库连接"""
    os.makedirs(os.path.dirname(DB_PATH), exist_ok=True)
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def init_db():
    """初始化数据库表"""
    conn = get_conn()
    c = conn.cursor()

    # 筛选记录表
    c.execute("""
        CREATE TABLE IF NOT EXISTS screen_records (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            candidate_name TEXT,
            job_title TEXT,
            job_category TEXT,
            total_score REAL,
            level TEXT,
            conclusion TEXT,
            skill_score REAL,
            education_score REAL,
            experience_score REAL,
            bonus_score REAL,
            matched_skills TEXT,
            missing_skills TEXT,
            suggestion TEXT,
            created_at TEXT
        )
    """)

    # 操作日志表
    c.execute("""
        CREATE TABLE IF NOT EXISTS operation_logs (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            action TEXT,
            detail TEXT,
            created_at TEXT
        )
    """)

    conn.commit()
    conn.close()


def add_screen_record(record: dict):
    """添加一条筛选记录"""
    conn = get_conn()
    c = conn.cursor()
    now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    c.execute("""
        INSERT INTO screen_records
        (candidate_name, job_title, job_category, total_score, level, conclusion,
         skill_score, education_score, experience_score, bonus_score,
         matched_skills, missing_skills, suggestion, created_at)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
    """, (
        record.get("candidate", ""),
        record.get("job_title", ""),
        record.get("job_category", ""),
        record.get("total_score", 0),
        record.get("level", ""),
        record.get("conclusion", ""),
        record.get("dimensions", {}).get("skill", {}).get("score", 0),
        record.get("dimensions", {}).get("education", {}).get("score", 0),
        record.get("dimensions", {}).get("experience", {}).get("score", 0),
        record.get("dimensions", {}).get("bonus", {}).get("score", 0),
        json.dumps(record.get("matched_skills", []), ensure_ascii=False),
        json.dumps(record.get("missing_skills", []), ensure_ascii=False),
        record.get("suggestion", ""),
        now,
    ))
    conn.commit()
    conn.close()


def get_recent_records(limit: int = 20) -> list:
    """获取最近的筛选记录"""
    conn = get_conn()
    c = conn.cursor()
    c.execute("SELECT * FROM screen_records ORDER BY id DESC LIMIT ?", (limit,))
    rows = c.fetchall()
    conn.close()
    return [dict(row) for row in rows]


def get_record_count() -> int:
    """获取筛选记录总数"""
    conn = get_conn()
    c = conn.cursor()
    c.execute("SELECT COUNT(*) FROM screen_records")
    count = c.fetchone()[0]
    conn.close()
    return count


def add_log(action: str, detail: str = ""):
    """添加操作日志"""
    conn = get_conn()
    c = conn.cursor()
    now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    c.execute("INSERT INTO operation_logs (action, detail, created_at) VALUES (?, ?, ?)",
              (action, detail, now))
    conn.commit()
    conn.close()


def get_recent_logs(limit: int = 50) -> list:
    """获取最近的操作日志"""
    conn = get_conn()
    c = conn.cursor()
    c.execute("SELECT * FROM operation_logs ORDER BY id DESC LIMIT ?", (limit,))
    rows = c.fetchall()
    conn.close()
    return [dict(row) for row in rows]


# 初始化
init_db()
