# quota_manager.py
import sqlite3
from datetime import datetime, date, timedelta
from typing import Dict, List, Optional

class QuotaManager:
    def __init__(self):
        self.db_path = "buffett_users.db"
        self.free_limits = {
            'weekly_analyses': 3,
            'daily_chatgpt': 0,  # No ChatGPT for free users
        }
        self.premium_limits = {
            'daily_chatgpt': 5,
        }
    
    def check_analysis_quota(self, user_email: str, is_premium: bool) -> Dict:
        """Check weekly analysis quota for user"""
        if is_premium:
            return {"allowed": True, "remaining": "unlimited", "limit": "unlimited"}
        
        conn = sqlite3.connect(self.db_path)
        try:
            user = conn.execute(
                "SELECT analysis_count_weekly, last_weekly_reset FROM users WHERE email = ?",
                (user_email,)
            ).fetchone()
            
            if not user:
                return {"allowed": False, "remaining": 0, "limit": self.free_limits['weekly_analyses']}
            
            count, last_reset = user[0], user[1]
            
            # Reset weekly counter if needed (every Monday)
            if self._should_reset_weekly(last_reset):
                count = 0
                conn.execute(
                    "UPDATE users SET analysis_count_weekly = 0, last_weekly_reset = ? WHERE email = ?",
                    (date.today().isoformat(), user_email)
                )
                conn.commit()
            
            limit = self.free_limits['weekly_analyses']
            remaining = max(0, limit - count)
            
            return {
                "allowed": count < limit,
                "remaining": remaining,
                "limit": limit,
                "used": count
            }
        except Exception as e:
            print(f"Error checking analysis quota: {e}")
            return {"allowed": False, "remaining": 0, "limit": self.free_limits['weekly_analyses']}
        finally:
            conn.close()
    
    def increment_analysis_usage(self, user_email: str, ticker: str = "", buffett_score: float = 0.0, owner_earnings: float = 0.0):
        """Increment weekly analysis counter and save to history"""
        conn = sqlite3.connect(self.db_path)
        try:
            # Increment weekly counter
            conn.execute(
                "UPDATE users SET analysis_count_weekly = analysis_count_weekly + 1 WHERE email = ?",
                (user_email,)
            )
            
            # Save to analysis history
            conn.execute(
                """INSERT INTO analysis_history 
                   (user_email, ticker, analysis_type, buffett_score, owner_earnings) 
                   VALUES (?, ?, 'standard', ?, ?)""",
                (user_email, ticker, buffett_score, owner_earnings)
            )
            
            conn.commit()
            print(f"✅ Analysis usage incremented for {user_email}: {ticker}")
        except Exception as e:
            print(f"Error incrementing analysis usage: {e}")
        finally:
            conn.close()
    
    def check_chatgpt_quota(self, user_email: str, is_premium: bool, is_professional: bool) -> Dict:
        """Check daily ChatGPT quota for user"""
        if is_professional:
            return {"allowed": True, "remaining": "unlimited", "limit": "unlimited"}
        
        conn = sqlite3.connect(self.db_path)
        try:
            user = conn.execute(
                "SELECT chatgpt_count_daily, last_daily_reset FROM users WHERE email = ?",
                (user_email,)
            ).fetchone()
            
            if not user:
                return {"allowed": False, "remaining": 0, "limit": 0}
            
            count, last_reset = user[0], user[1]
            
            # Reset daily counter if needed
            if self._should_reset_daily(last_reset):
                count = 0
                conn.execute(
                    "UPDATE users SET chatgpt_count_daily = 0, last_daily_reset = ? WHERE email = ?",
                    (date.today().isoformat(), user_email)
                )
                conn.commit()
            
            if not is_premium:
                return {"allowed": False, "remaining": 0, "limit": 0}
            
            limit = self.premium_limits['daily_chatgpt']
            remaining = max(0, limit - count)
            
            return {
                "allowed": count < limit,
                "remaining": remaining,
                "limit": limit,
                "used": count
            }
        except Exception as e:
            print(f"Error checking ChatGPT quota: {e}")
            return {"allowed": False, "remaining": 0, "limit": 0}
        finally:
            conn.close()
    
    def increment_chatgpt_usage(self, user_email: str):
        """Increment daily ChatGPT counter"""
        conn = sqlite3.connect(self.db_path)
        try:
            conn.execute(
                "UPDATE users SET chatgpt_count_daily = chatgpt_count_daily + 1 WHERE email = ?",
                (user_email,)
            )
            conn.commit()
            print(f"✅ ChatGPT usage incremented for {user_email}")
        except Exception as e:
            print(f"Error incrementing ChatGPT usage: {e}")
        finally:
            conn.close()
    
    def get_user_usage_summary(self, user_email: str) -> Dict:
        """Get comprehensive usage summary for a user"""
        conn = sqlite3.connect(self.db_path)
        try:
            # Get current usage
            user = conn.execute(
                """SELECT analysis_count_weekly, last_weekly_reset, 
                          chatgpt_count_daily, last_daily_reset, subscription_tier 
                   FROM users WHERE email = ?""",
                (user_email,)
            ).fetchone()
            
            if not user:
                return {}
            
            analysis_count, weekly_reset, chatgpt_count, daily_reset, tier = user
            
            # Get total historical analyses
            total_analyses = conn.execute(
                "SELECT COUNT(*) FROM analysis_history WHERE user_email = ?",
                (user_email,)
            ).fetchone()[0]
            
            # Get recent analyses
            recent_analyses = conn.execute(
                """SELECT ticker, buffett_score, created_at FROM analysis_history 
                   WHERE user_email = ? ORDER BY created_at DESC LIMIT 5""",
                (user_email,)
            ).fetchall()
            
            return {
                'current_week_analyses': analysis_count,
                'current_day_chatgpt': chatgpt_count,
                'total_analyses_ever': total_analyses,
                'subscription_tier': tier,
                'recent_analyses': [
                    {'ticker': r[0], 'score': r[1], 'date': r[2]} 
                    for r in recent_analyses
                ],
                'weekly_reset_due': self._should_reset_weekly(weekly_reset),
                'daily_reset_due': self._should_reset_daily(daily_reset)
            }
        except Exception as e:
            print(f"Error getting usage summary: {e}")
            return {}
        finally:
            conn.close()
    
    def _should_reset_weekly(self, last_reset: str) -> bool:
        """Check if weekly counter should reset (every Monday)"""
        if not last_reset:
            return True
        
        try:
            last_date = datetime.fromisoformat(last_reset).date()
            today = date.today()
            
            # Find Monday of this week
            days_since_monday = today.weekday()  # Monday = 0
            this_monday = today - timedelta(days=days_since_monday)
            
            return last_date < this_monday
        except:
            return True
    
    def _should_reset_daily(self, last_reset: str) -> bool:
        """Check if daily counter should reset"""
        if not last_reset:
            return True
        
        try:
            last_date = datetime.fromisoformat(last_reset).date()
            return last_date < date.today()
        except:
            return True
    
    def reset_user_quotas(self, user_email: str):
        """Manually reset user quotas (admin function)"""
        conn = sqlite3.connect(self.db_path)
        try:
            conn.execute(
                """UPDATE users 
                   SET analysis_count_weekly = 0, chatgpt_count_daily = 0,
                       last_weekly_reset = ?, last_daily_reset = ?
                   WHERE email = ?""",
                (date.today().isoformat(), date.today().isoformat(), user_email)
            )
            conn.commit()
            print(f"✅ Quotas reset for {user_email}")
        except Exception as e:
            print(f"Error resetting quotas: {e}")
        finally:
            conn.close()