# auth_manager.py
import streamlit as st
import sqlite3
from datetime import datetime, timedelta
from typing import Optional, Dict, Any
import os

class AuthManager:
    def __init__(self):
        self.db_path = "buffett_users.db"
        self.init_database()
    
    def init_database(self):
        """Initialize SQLite database for user management"""
        conn = sqlite3.connect(self.db_path)
        try:
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
            
            conn.execute('''
                CREATE TABLE IF NOT EXISTS analysis_history (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    user_email TEXT,
                    ticker TEXT,
                    analysis_type TEXT,
                    buffett_score REAL,
                    owner_earnings REAL,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    FOREIGN KEY (user_email) REFERENCES users(email)
                )
            ''')
            
            conn.commit()
            print("✅ Database tables created/verified successfully")
        except Exception as e:
            print(f"Database initialization error: {e}")
        finally:
            conn.close()
    
    def handle_login(self):
        """Handle user authentication with Streamlit native auth"""
        # Check if user is already logged in
        if hasattr(st, 'user') and st.user and hasattr(st.user, 'email') and st.user.email:
            # User is authenticated, register/update in database
            self.register_or_update_user(
                email=st.user.email,
                name=getattr(st.user, 'name', 'Unknown User')
            )
            return True
        else:
            # Show login UI
            col1, col2, col3 = st.columns([1, 2, 1])
            with col2:
                st.markdown("### 💰 Access Buffett's Investment Wisdom")
                st.markdown("*Analyze companies like Warren Buffett with AI-powered insights*")
                
                # Check if native auth is available
                if hasattr(st, 'login'):
                    if st.button("🚀 Sign in with Google", use_container_width=True):
                        try:
                            st.login("google")
                        except Exception as e:
                            st.error(f"Login error: {e}")
                            st.info("Make sure your secrets.toml is configured with Google OAuth credentials")
                else:
                    st.error("Native authentication not available. Please ensure you have Streamlit >= 1.42.0")
                    return False
                
                # Show value proposition while user is not logged in
                st.markdown("---")
                st.markdown("""
                **What you'll unlock:**
                - 🧮 Owner Earnings analysis (Buffett's 1986 method)
                - 🎯 Circle of Competence filtering  
                - 📊 Risk assessment with Altman Z-scores
                - 🤖 AI-powered investment insights
                - 📄 Professional PDF reports
                - 📈 Look-Through Earnings analysis
                """)
                
                # Show sample analysis
                with st.expander("👀 See Sample Analysis"):
                    st.markdown("""
                    **Coca-Cola (KO) - Sample Results:**
                    - Owner Earnings: $9.2B
                    - Altman Z-Score: 3.4 (Safe)
                    - Buffett Score: 87.3/100
                    - Circle of Competence: ✅ PASS
                    - Capital Preservation: 91.2/100
                    """)
            
            return False
    
    def register_or_update_user(self, email: str, name: str):
        """Register new user or update existing user"""
        conn = sqlite3.connect(self.db_path)
        try:
            # Check if user exists
            user = conn.execute(
                "SELECT * FROM users WHERE email = ?", (email,)
            ).fetchone()
            
            if user:
                # Update last login
                conn.execute(
                    "UPDATE users SET last_login = ? WHERE email = ?",
                    (datetime.now().isoformat(), email)
                )
            else:
                # Register new user with initialized quotas
                conn.execute(
                    """INSERT INTO users 
                       (email, name, last_login, last_weekly_reset, last_daily_reset) 
                       VALUES (?, ?, ?, ?, ?)""",
                    (email, name, datetime.now().isoformat(), 
                     datetime.now().date().isoformat(), datetime.now().date().isoformat())
                )
                print(f"✅ New user registered: {email}")
            
            conn.commit()
        except Exception as e:
            print(f"Database error in register_or_update_user: {e}")
        finally:
            conn.close()
    
    def get_user_info(self, email: str) -> Optional[Dict[str, Any]]:
        """Get complete user information from database"""
        conn = sqlite3.connect(self.db_path)
        try:
            user = conn.execute("SELECT * FROM users WHERE email = ?", (email,)).fetchone()
            
            if user:
                return {
                    'id': user[0],
                    'email': user[1],
                    'name': user[2],
                    'subscription_tier': user[3],
                    'subscription_id': user[4],
                    'subscription_end_date': user[5],
                    'created_at': user[6],
                    'last_login': user[7],
                    'analysis_count_weekly': user[8],
                    'last_weekly_reset': user[9],
                    'chatgpt_count_daily': user[10],
                    'last_daily_reset': user[11]
                }
            return None
        except Exception as e:
            print(f"Database error in get_user_info: {e}")
            return None
        finally:
            conn.close()
    
    def is_premium_user(self, email: str) -> bool:
        """Check if user has active premium or professional subscription"""
        user = self.get_user_info(email)
        if not user:
            return False
        
        tier = user['subscription_tier']
        if tier in ['premium', 'professional']:
            # Check if subscription is still active
            if user['subscription_end_date']:
                try:
                    end_date = datetime.fromisoformat(user['subscription_end_date'])
                    return end_date > datetime.now()
                except:
                    return False
        
        return False
    
    def is_professional_user(self, email: str) -> bool:
        """Check if user has active professional subscription"""
        user = self.get_user_info(email)
        if not user:
            return False
        
        if user['subscription_tier'] == 'professional':
            if user['subscription_end_date']:
                try:
                    end_date = datetime.fromisoformat(user['subscription_end_date'])
                    return end_date > datetime.now()
                except:
                    return False
        
        return False
    
    def handle_logout(self):
        """Handle user logout"""
        if hasattr(st, 'logout'):
            if st.button("🚪 Logout"):
                st.logout()
                st.rerun()
        else:
            st.warning("Logout not available - check Streamlit version")
    
    def update_subscription(self, email: str, tier: str, subscription_id: str = None, days: int = 30):
        """Update user subscription status"""
        conn = sqlite3.connect(self.db_path)
        try:
            end_date = (datetime.now() + timedelta(days=days)).isoformat()
            
            conn.execute(
                """UPDATE users 
                   SET subscription_tier = ?, subscription_id = ?, subscription_end_date = ?
                   WHERE email = ?""",
                (tier, subscription_id, end_date, email)
            )
            conn.commit()
            print(f"✅ Updated subscription for {email}: {tier}")
        except Exception as e:
            print(f"Error updating subscription: {e}")
        finally:
            conn.close()
    
    def get_user_stats(self):
        """Get user statistics for admin dashboard"""
        conn = sqlite3.connect(self.db_path)
        try:
            total_users = conn.execute("SELECT COUNT(*) FROM users").fetchone()[0]
            free_users = conn.execute("SELECT COUNT(*) FROM users WHERE subscription_tier = 'free'").fetchone()[0]
            premium_users = conn.execute("SELECT COUNT(*) FROM users WHERE subscription_tier = 'premium'").fetchone()[0]
            professional_users = conn.execute("SELECT COUNT(*) FROM users WHERE subscription_tier = 'professional'").fetchone()[0]
            
            return {
                'total': total_users,
                'free': free_users,
                'premium': premium_users,
                'professional': professional_users
            }
        except Exception as e:
            print(f"Error getting user stats: {e}")
            return {'total': 0, 'free': 0, 'premium': 0, 'professional': 0}
        finally:
            conn.close()