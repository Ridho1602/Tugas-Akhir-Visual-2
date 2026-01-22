import mysql.connector

DB_CONFIG = {
    "host": "127.0.0.1",
    "user": "root",
    "password": "",
    "database": "ojol",
    "port": 3306
}

def get_conn():
    return mysql.connector.connect(**DB_CONFIG)

def select_rows(query, params=None):
    conn = get_conn()
    try:
        cur = conn.cursor(dictionary=True)
        cur.execute(query, params or ())
        return cur.fetchall()
    finally:
        conn.close()

def execute(query, params=None):
    conn = get_conn()
    try:
        cur = conn.cursor()
        cur.execute(query, params or ())
        conn.commit()
        return cur.rowcount
    finally:
        conn.close()
