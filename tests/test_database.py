# test_database.py
import sqlite3
from datetime import datetime

def init_database():
    conn = sqlite3.connect('buffett_users.db')
    
    # Create users table
    conn.execute('''
        CREATE TABLE IF NOT EXISTS users (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            email TEXT UNIQUE NOT NULL,
            name TEXT,
            subscription_tier TEXT DEFAULT 'free',
            subscription_id TEXT,
            subscription_end_date TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            last_login TIMESTAMP,
            analysis_count_weekly INTEGER DEFAULT 0,
            last_weekly_reset DATE,
            chatgpt_count_daily INTEGER DEFAULT 0,
            last_daily_reset DATE
        )
    ''')
    
    conn.commit()
    conn.close()
    print("✅ Database initialized successfully!")

if __name__ == "__main__":
    init_database()