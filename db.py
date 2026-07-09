"""
db.py
-----
إدارة قاعدة بيانات SQLite المحلية اللي بتخزن كل المناقصات اللي اتبحث عنها
وتفاصيلها والشركات الفايزة فيها.
"""

import sqlite3
import os

DB_PATH = os.path.join(os.path.dirname(__file__), "data", "monaqasat.db")


def get_connection():
    os.makedirs(os.path.dirname(DB_PATH), exist_ok=True)
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def init_db():
    conn = get_connection()
    cur = conn.cursor()

    cur.execute("""
        CREATE TABLE IF NOT EXISTS tenders (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            tender_id TEXT UNIQUE,          -- الرقم في نهاية رابط التفاصيل (مثال 658834)
            tender_number TEXT,             -- رقم المناقصة (مثال 2580/2026)
            tender_number_at_ministry TEXT,
            subject TEXT,                   -- موضوع/صنف المناقصة
            ministry TEXT,
            sector_type TEXT,
            tender_type TEXT,
            envelopes_system TEXT,
            publish_date TEXT,
            closing_date TEXT,
            technical_open_date TEXT,
            financial_open_date TEXT,
            award_date TEXT,
            document_value TEXT,
            tender_bond TEXT,
            awarded_amount TEXT,
            details_url TEXT,
            companies_url TEXT,
            first_searched_with TEXT,       -- أول كلمة بحث لقينا بيها المناقصة دي
            fetched_at TEXT DEFAULT (datetime('now'))
        )
    """)

    cur.execute("""
        CREATE TABLE IF NOT EXISTS awarded_companies (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            tender_id TEXT,                 -- FK -> tenders.tender_id
            company_name TEXT,
            cr_number TEXT,
            approved_value TEXT,
            financial_result TEXT,
            approved_items TEXT,
            FOREIGN KEY (tender_id) REFERENCES tenders(tender_id)
        )
    """)

    cur.execute("""
        CREATE TABLE IF NOT EXISTS technically_opened_companies (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            tender_id TEXT,
            company_name TEXT,
            cr_number TEXT,
            FOREIGN KEY (tender_id) REFERENCES tenders(tender_id)
        )
    """)

    cur.execute("""
        CREATE TABLE IF NOT EXISTS search_log (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            search_term TEXT,
            results_count INTEGER,
            searched_at TEXT DEFAULT (datetime('now'))
        )
    """)

    conn.commit()
    conn.close()


def tender_exists(tender_id: str) -> bool:
    conn = get_connection()
    cur = conn.cursor()
    cur.execute("SELECT 1 FROM tenders WHERE tender_id = ?", (tender_id,))
    row = cur.fetchone()
    conn.close()
    return row is not None


def save_tender(tender: dict, companies: list, tech_companies: list, search_term: str):
    conn = get_connection()
    cur = conn.cursor()

    cur.execute("""
        INSERT OR IGNORE INTO tenders (
            tender_id, tender_number, tender_number_at_ministry, subject, ministry,
            sector_type, tender_type, envelopes_system, publish_date, closing_date,
            technical_open_date, financial_open_date, award_date, document_value,
            tender_bond, awarded_amount, details_url, companies_url, first_searched_with
        ) VALUES (:tender_id, :tender_number, :tender_number_at_ministry, :subject, :ministry,
                  :sector_type, :tender_type, :envelopes_system, :publish_date, :closing_date,
                  :technical_open_date, :financial_open_date, :award_date, :document_value,
                  :tender_bond, :awarded_amount, :details_url, :companies_url, :first_searched_with)
    """, {**tender, "first_searched_with": search_term})

    for c in companies:
        cur.execute("""
            INSERT INTO awarded_companies (tender_id, company_name, cr_number, approved_value, financial_result, approved_items)
            VALUES (?, ?, ?, ?, ?, ?)
        """, (tender["tender_id"], c["company_name"], c["cr_number"], c["approved_value"], c["financial_result"], c["approved_items"]))

    for c in tech_companies:
        cur.execute("""
            INSERT INTO technically_opened_companies (tender_id, company_name, cr_number)
            VALUES (?, ?, ?)
        """, (tender["tender_id"], c["company_name"], c["cr_number"]))

    conn.commit()
    conn.close()


def log_search(term: str, count: int):
    conn = get_connection()
    cur = conn.cursor()
    cur.execute("INSERT INTO search_log (search_term, results_count) VALUES (?, ?)", (term, count))
    conn.commit()
    conn.close()


def search_local(term: str):
    """بحث في القاعدة المحلية (اللي اتحفظت قبل كده) عن أي مناقصة فيها الكلمة دي في الصنف."""
    conn = get_connection()
    cur = conn.cursor()
    cur.execute("SELECT * FROM tenders WHERE subject LIKE ?", (f"%{term}%",))
    tenders = [dict(r) for r in cur.fetchall()]
    for t in tenders:
        cur.execute("SELECT * FROM awarded_companies WHERE tender_id = ?", (t["tender_id"],))
        t["awarded_companies"] = [dict(r) for r in cur.fetchall()]
    conn.close()
    return tenders


if __name__ == "__main__":
    init_db()
    print(f"تم إنشاء قاعدة البيانات في: {DB_PATH}")
