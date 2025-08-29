# test_sqlite.py
import sqlite3
import os

try:
    # Test database creation
    conn = sqlite3.connect(':memory:')  # In-memory database for testing
    conn.execute('CREATE TABLE test (id INTEGER PRIMARY KEY, name TEXT)')
    conn.execute('INSERT INTO test (name) VALUES (?)', ('Test User',))
    result = conn.execute('SELECT * FROM test').fetchone()
    conn.close()
    
    print("✅ SQLite3 is working correctly!")
    print(f"SQLite version: {sqlite3.sqlite_version}")
    print(f"Test result: {result}")
except Exception as e:
    print(f"❌ SQLite3 error: {e}")