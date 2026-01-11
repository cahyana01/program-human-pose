import sqlite3
import datetime
import os

DB_NAME = "history.db"

def init_db():
    conn = sqlite3.connect(DB_NAME)
    c = conn.cursor()
    # History Table
    c.execute('''CREATE TABLE IF NOT EXISTS history
                 (id INTEGER PRIMARY KEY AUTOINCREMENT,
                  timestamp TEXT,
                  movement_type TEXT,
                  result TEXT,
                  image_path TEXT,
                  ref_path TEXT,
                  score REAL)''')
    
    # References Table
    c.execute('''CREATE TABLE IF NOT EXISTS references_table
                 (id INTEGER PRIMARY KEY AUTOINCREMENT,
                  movement_type TEXT,
                  filepath_orig TEXT,
                  filepath_annotated TEXT,
                  timestamp TEXT)''')
                  
    conn.commit()
    
    # Migration: Add ref_path column if it doesn't exist
    try:
        c.execute("ALTER TABLE history ADD COLUMN ref_path TEXT")
        conn.commit()
    except sqlite3.OperationalError:
        pass # Column already exists

    try:
        c.execute("ALTER TABLE history ADD COLUMN score REAL")
        conn.commit()
    except sqlite3.OperationalError:
        pass # Column already exists
        
    conn.close()

# --- History Methods ---
def add_record(movement_type, result, image_path="", ref_path="", score=0.0):
    conn = sqlite3.connect(DB_NAME)
    c = conn.cursor()
    timestamp = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    c.execute("INSERT INTO history (timestamp, movement_type, result, image_path, ref_path, score) VALUES (?, ?, ?, ?, ?, ?)",
              (timestamp, movement_type, result, image_path, ref_path, score))
    conn.commit()
    conn.close()

def get_history():
    conn = sqlite3.connect(DB_NAME)
    conn.row_factory = sqlite3.Row
    c = conn.cursor()
    c.execute("SELECT * FROM history ORDER BY id DESC")
    rows = c.fetchall()
    conn.close()
    return [dict(row) for row in rows]

def delete_history_item(item_id):
    conn = sqlite3.connect(DB_NAME)
    c = conn.cursor()
    c.execute("DELETE FROM history WHERE id=?", (item_id,))
    conn.commit()
    conn.close()

def clear_history():
    conn = sqlite3.connect(DB_NAME)
    c = conn.cursor()
    c.execute("DELETE FROM history")
    conn.commit()
    conn.close()

# --- Reference Methods ---
def add_reference(movement_type, filepath_orig, filepath_annotated):
    conn = sqlite3.connect(DB_NAME)
    c = conn.cursor()
    timestamp = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    c.execute("INSERT INTO references_table (movement_type, filepath_orig, filepath_annotated, timestamp) VALUES (?, ?, ?, ?)",
              (movement_type, filepath_orig, filepath_annotated, timestamp))
    conn.commit()
    conn.close()

def get_references(movement_type=None):
    conn = sqlite3.connect(DB_NAME)
    conn.row_factory = sqlite3.Row
    c = conn.cursor()
    if movement_type:
        c.execute("SELECT * FROM references_table WHERE movement_type=? ORDER BY id DESC", (movement_type,))
    else:
        c.execute("SELECT * FROM references_table ORDER BY id DESC")
    rows = c.fetchall()
    conn.close()
    return [dict(row) for row in rows]

def delete_reference(ref_id):
    conn = sqlite3.connect(DB_NAME)
    conn.row_factory = sqlite3.Row
    c = conn.cursor()
    # Get paths first to delete files
    c.execute("SELECT filepath_orig, filepath_annotated FROM references_table WHERE id=?", (ref_id,))
    row = c.fetchone()
    if row:
        c.execute("DELETE FROM references_table WHERE id=?", (ref_id,))
        conn.commit()
    conn.close()
    return dict(row) if row else None
