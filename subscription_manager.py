# subscription_manager.py
import streamlit as st
import sqlite3
from datetime import datetime, timedelta
from typing import Optional

# Only import stripe if available (for development without Stripe)
try:
    import stripe
    STRIPE_AVAILABLE = True
except ImportError:
    STRIPE_AVAILABLE = False
    st.warning("Stripe not installed. Install with: pip install stripe")

class SubscriptionManager:
    def __init__(self):
        self.db_path = "buffett_users.db"
        
        if STRIPE_AVAILABLE:
            # Get Stripe configuration from secrets
            try:
                stripe.api_key = st.secrets.get("stripe_api_key")
                self.stripe_configured = bool(st.secrets.get("stripe_api_key"))
            except:
                self.stripe_configured = False
                
            self.price_ids = {
                "premium": st.secrets.get("stripe_premium_price_id", "price_premium_default"),
                "professional": st.secrets.get("stripe_professional_price_id", "price_professional_default")
            }
            
            self.app_url = st.secrets.get("app_url", "http://localhost:8501")
        else:
            self.stripe_configured = False
    
    def show_upgrade_modal(self, user_email: str, current_tier: str = "free"):
        """Show upgrade modal with pricing plans"""
        st.markdown("## 🚀 Unlock the Full Power of Buffett Analysis")
        
        # Create three columns for the plans
        col1, col2, col3 = st.columns(3)
        
        with col1:
            st.markdown("""
            ### 🆓 Free Plan
            **Current Plan** *(if free)*
            
            **What you get:**
            - 3 company analyses/week
            - S&P 500 companies only
            - Basic Owner Earnings
            - Basic Altman Z-Score
            - Circle of Competence (3 sectors)
            
            **Perfect for:** Getting started with Buffett-style investing
            """)
            
            if current_tier != "free":
                if st.button("⬇️ Downgrade to Free", key="downgrade_free", use_container_width=True):
                    self._update_subscription(user_email, "free", None)
                    st.success("Downgraded to Free plan")
                    st.rerun()
        
        with col2:
            st.markdown("""
            ### ⭐ Premium Plan
            **$49/month**
            
            **Everything in Free plus:**
            - ✨ **Unlimited analyses**
            - 🌍 **Any public company**
            - 📊 **Advanced risk metrics**
            - 💡 **Look-Through Earnings**
            - 🔄 **Contrarian analysis**
            - 🤖 **AI insights (5/day)**
            - 📄 **PDF report exports**
            
            **Perfect for:** Serious individual investors
            """)
            
            if current_tier != "premium":
                if self.stripe_configured:
                    if st.button("🚀 Upgrade to Premium", key="upgrade_premium", use_container_width=True):
                        checkout_url = self.create_checkout_session(user_email, "premium")
                        if checkout_url:
                            st.markdown(f"[Complete Payment →]({checkout_url})")
                        else:
                            st.error("Payment setup error. Please try again.")
                else:
                    st.button("🚀 Upgrade to Premium", key="upgrade_premium_demo", use_container_width=True, disabled=True)
                    st.caption("*Demo mode - Stripe not configured*")
        
        with col3:
            st.markdown("""
            ### 🏆 Professional Plan
            **$149/month**
            
            **Everything in Premium plus:**
            - 🤖 **Unlimited AI analysis**
            - 🔧 **Greenwald CapEx method**
            - 📊 **Bulk CSV analysis**
            - 🔗 **API access**
            - 💼 **Portfolio analysis**
            - 📊 **Excel/JSON exports**
            - 🎯 **Priority support**
            
            **Perfect for:** Investment professionals & firms
            """)
            
            if current_tier != "professional":
                if self.stripe_configured:
                    if st.button("🏆 Upgrade to Professional", key="upgrade_professional", use_container_width=True):
                        checkout_url = self.create_checkout_session(user_email, "professional")
                        if checkout_url:
                            st.markdown(f"[Complete Payment →]({checkout_url})")
                        else:
                            st.error("Payment setup error. Please try again.")
                else:
                    st.button("🏆 Upgrade to Professional", key="upgrade_professional_demo", use_container_width=True, disabled=True)
                    st.caption("*Demo mode - Stripe not configured*")
        
        # Show testimonials or value props
        st.markdown("---")
        st.markdown("### 💬 What Users Say")
        
        col1, col2 = st.columns(2)
        with col1:
            st.markdown("""
            > "This app saved me hours of manual calculations. The Owner Earnings analysis is spot-on with Buffett's methodology."
            > 
            > — Sarah M., Portfolio Manager
            """)
        
        with col2:
            st.markdown("""
            > "The AI insights help me understand what Buffett would think about each investment. Game changer!"
            > 
            > — Mike D., Individual Investor
            """)
        
        # Money back guarantee
        st.info("💰 **30-day money-back guarantee** • Cancel anytime • No hidden fees")
        
        # Demo upgrade for testing (remove in production)
        if not self.stripe_configured:
            st.markdown("---")
            st.markdown("### 🧪 Demo Mode")
            col1, col2 = st.columns(2)
            with col1:
                if st.button("Demo: Upgrade to Premium", key="demo_premium"):
                    self._update_subscription(user_email, "premium", "demo_premium_123")
                    st.success("Demo: Upgraded to Premium!")
                    st.rerun()
            with col2:
                if st.button("Demo: Upgrade to Professional", key="demo_professional"):
                    self._update_subscription(user_email, "professional", "demo_professional_123")
                    st.success("Demo: Upgraded to Professional!")
                    st.rerun()
    
    def create_checkout_session(self, user_email: str, plan: str) -> Optional[str]:
        """Create Stripe checkout session"""
        if not STRIPE_AVAILABLE or not self.stripe_configured:
            return None
        
        try:
            price_id = self.price_ids.get(plan)
            if not price_id:
                st.error(f"Price ID not configured for {plan}")
                return None
            
            # Create checkout session
            checkout_session = stripe.checkout.Session.create(
                customer_email=user_email,
                payment_method_types=['card'],
                line_items=[{
                    'price': price_id,
                    'quantity': 1,
                }],
                mode='subscription',
                success_url=f"{self.app_url}?payment=success&session_id={{CHECKOUT_SESSION_ID}}",
                cancel_url=f"{self.app_url}?payment=cancelled",
                metadata={
                    'user_email': user_email,
                    'plan': plan,
                    'source': 'buffett_analyzer'
                },
                allow_promotion_codes=True,  # Allow discount codes
            )
            
            return checkout_session.url
            
        except Exception as e:
            st.error(f"Error creating checkout session: {str(e)}")
            print(f"Stripe error: {e}")
            return None
    
    def handle_successful_payment(self, session_id: str) -> bool:
        """Process successful payment callback"""
        if not STRIPE_AVAILABLE or not self.stripe_configured:
            return False
        
        try:
            # Retrieve the session from Stripe
            session = stripe.checkout.Session.retrieve(session_id)
            
            if session.payment_status == 'paid':
                user_email = session.metadata.get('user_email')
                plan = session.metadata.get('plan')
                subscription_id = session.subscription
                
                if user_email and plan:
                    self._update_subscription(user_email, plan, subscription_id)
                    st.success(f"🎉 Welcome to {plan.title()}! Your subscription is now active.")
                    return True
        except Exception as e:
            st.error(f"Error processing payment: {str(e)}")
            print(f"Payment processing error: {e}")
        
        return False
    
    def _update_subscription(self, email: str, tier: str, subscription_id: str, days: int = 30):
        """Update user subscription in database"""
        conn = sqlite3.connect(self.db_path)
        try:
            if tier == "free":
                # Downgrade to free
                conn.execute(
                    """UPDATE users 
                       SET subscription_tier = 'free', subscription_id = NULL, subscription_end_date = NULL
                       WHERE email = ?""",
                    (email,)
                )
            else:
                # Upgrade to paid plan
                end_date = (datetime.now() + timedelta(days=days)).isoformat()
                conn.execute(
                    """UPDATE users 
                       SET subscription_tier = ?, subscription_id = ?, subscription_end_date = ?
                       WHERE email = ?""",
                    (tier, subscription_id, end_date, email)
                )
            
            conn.commit()
            print(f"✅ Subscription updated for {email}: {tier}")
            
        except Exception as e:
            print(f"Error updating subscription: {e}")
        finally:
            conn.close()
    
    def check_subscription_status(self, email: str) -> dict:
        """Check current subscription status"""
        conn = sqlite3.connect(self.db_path)
        try:
            user = conn.execute(
                "SELECT subscription_tier, subscription_end_date FROM users WHERE email = ?",
                (email,)
            ).fetchone()
            
            if not user:
                return {"tier": "free", "active": False, "days_remaining": 0}
            
            tier, end_date = user
            
            if tier == "free":
                return {"tier": "free", "active": True, "days_remaining": None}
            
            if end_date:
                try:
                    end_datetime = datetime.fromisoformat(end_date)
                    now = datetime.now()
                    
                    if end_datetime > now:
                        days_remaining = (end_datetime - now).days
                        return {"tier": tier, "active": True, "days_remaining": days_remaining}
                    else:
                        # Subscription expired, downgrade to free
                        self._update_subscription(email, "free", None)
                        return {"tier": "free", "active": False, "days_remaining": 0}
                except:
                    return {"tier": "free", "active": False, "days_remaining": 0}
            
            return {"tier": tier, "active": True, "days_remaining": None}
            
        except Exception as e:
            print(f"Error checking subscription: {e}")
            return {"tier": "free", "active": False, "days_remaining": 0}
        finally:
            conn.close()
    
    def show_account_settings(self, user_email: str):
        """Show account settings and subscription management"""
        status = self.check_subscription_status(user_email)
        
        st.markdown("### ⚙️ Account Settings")
        
        col1, col2 = st.columns([2, 1])
        
        with col1:
            st.markdown(f"**Email:** {user_email}")
            st.markdown(f"**Current Plan:** {status['tier'].title()}")
            
            if status['active'] and status['days_remaining'] is not None:
                if status['days_remaining'] > 7:
                    st.success(f"✅ {status['days_remaining']} days remaining")
                elif status['days_remaining'] > 0:
                    st.warning(f"⚠️ {status['days_remaining']} days remaining")
                else:
                    st.error("❌ Subscription expired")
        
        with col2:
            if st.button("📊 View Usage Stats", key="view_usage"):
                st.session_state["show_usage_stats"] = True
            
            if st.button("💳 Manage Subscription", key="manage_sub"):
                st.session_state["show_upgrade_modal"] = True
        
        # Show usage stats if requested
        if st.session_state.get("show_usage_stats", False):
            self._show_usage_stats(user_email)
    
    def _show_usage_stats(self, user_email: str):
        """Show detailed usage statistics"""
        from quota_manager import QuotaManager
        quota_manager = QuotaManager()
        usage = quota_manager.get_user_usage_summary(user_email)
        
        if usage:
            st.markdown("### 📊 Usage Statistics")
            
            col1, col2, col3, col4 = st.columns(4)
            
            with col1:
                st.metric("This Week", usage['current_week_analyses'], "Analyses")
            with col2:
                st.metric("Today", usage['current_day_chatgpt'], "AI Queries")
            with col3:
                st.metric("All Time", usage['total_analyses_ever'], "Total Analyses")
            with col4:
                st.metric("Plan", usage['subscription_tier'].title(), "Current")
            
            if usage['recent_analyses']:
                st.markdown("### 📈 Recent Analyses")
                for analysis in usage['recent_analyses'][:10]:
                    col1, col2, col3 = st.columns([2, 2, 1])
                    with col1:
                        st.write(f"**{analysis['ticker']}**")
                    with col2:
                        st.write(f"Score: {analysis['score']:.1f}/100")
                    with col3:
                        st.write(analysis['date'][:10])