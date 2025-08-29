# feature_gates.py
import streamlit as st
from typing import List, Optional, Dict
import pandas as pd

class FeatureGates:
    def __init__(self, quota_manager, auth_manager):
        self.quota_manager = quota_manager
        self.auth_manager = auth_manager
        
        # S&P 500 tickers (simplified list - you can expand this)
        self.sp500_tickers = {
            'AAPL', 'MSFT', 'AMZN', 'GOOGL', 'GOOG', 'TSLA', 'META', 'NVDA', 
            'BRK.A', 'BRK.B', 'UNH', 'JNJ', 'JPM', 'V', 'PG', 'HD', 'CVX', 
            'MA', 'PFE', 'ABBV', 'BAC', 'KO', 'PEP', 'COST', 'TMO', 'AVGO',
            'WMT', 'DIS', 'ABT', 'CRM', 'DHR', 'VZ', 'ADBE', 'NEE', 'CMCSA',
            'XOM', 'NKE', 'LIN', 'NFLX', 'QCOM', 'TXN', 'RTX', 'UPS', 'HON',
            'LOW', 'IBM', 'SPGI', 'CAT', 'AXP', 'GS', 'BKNG', 'DE', 'INTU'
        }
    
    def check_analysis_permission(self, user_email: str, is_premium: bool, show_ui: bool = True) -> bool:
        """Check if user can start a new analysis"""
        quota_info = self.quota_manager.check_analysis_quota(user_email, is_premium)
        
        if not quota_info["allowed"]:
            if show_ui:
                st.error("🚫 Weekly analysis limit reached!")
                
                col1, col2 = st.columns(2)
                with col1:
                    st.info(f"**Free Plan:** {quota_info['used']}/{quota_info['limit']} analyses used this week")
                    st.markdown("*Resets every Monday*")
                
                with col2:
                    if st.button("🚀 Upgrade to Premium", key="upgrade_from_limit"):
                        st.session_state["show_upgrade_modal"] = True
                        st.rerun()
                
                st.markdown("**Premium Benefits:**")
                st.markdown("- ✨ Unlimited company analyses")
                st.markdown("- 🌍 Any public company (not just S&P 500)")
                st.markdown("- 📊 Advanced risk metrics")
                st.markdown("- 🤖 AI-powered insights")
            
            return False
        
        if not is_premium and show_ui:
            st.info(f"📊 **Free Plan:** {quota_info['remaining']} analyses remaining this week")
        
        return True
    
    def check_ticker_access(self, ticker: str, is_premium: bool, show_ui: bool = True) -> bool:
        """Check if user can analyze this specific ticker"""
        if is_premium:
            return True
        
        ticker_upper = ticker.upper().strip()
        
        if ticker_upper not in self.sp500_tickers:
            if show_ui:
                st.error(f"🔒 **{ticker_upper} requires Premium subscription**")
                
                col1, col2 = st.columns(2)
                with col1:
                    st.info("**Free users** can analyze S&P 500 companies only")
                    st.markdown("**Available free tickers:**")
                    st.code("AAPL, MSFT, KO, JNJ, BRK.B, PG, V, MA, NVDA, AMZN")
                
                with col2:
                    if st.button("🚀 Upgrade to Premium", key=f"upgrade_ticker_{ticker}"):
                        st.session_state["show_upgrade_modal"] = True
                        st.rerun()
            
            return False
        
        return True
    
    def check_advanced_risk_metrics(self, is_premium: bool, show_ui: bool = True) -> bool:
        """Gate advanced risk metrics (Max Drawdown, Volatility)"""
        if is_premium:
            return True
        
        if show_ui:
            st.markdown("### 🔒 Advanced Risk Analysis (Premium)")
            
            col1, col2 = st.columns([2, 1])
            with col1:
                st.info("**Max Drawdown & Volatility Analysis** helps assess capital preservation - a key Buffett principle")
                st.markdown("These metrics show:")
                st.markdown("- Worst historical price declines")
                st.markdown("- Stock price stability over time") 
                st.markdown("- Risk-adjusted investment quality")
            
            with col2:
                if st.button("🔓 Unlock Risk Metrics", key="unlock_risk"):
                    st.session_state["show_upgrade_modal"] = True
                    st.rerun()
        
        return False
    
    def check_look_through_earnings(self, is_premium: bool, show_ui: bool = True) -> bool:
        """Gate Look-Through Earnings calculation (Buffett 1991)"""
        if is_premium:
            return True
        
        if show_ui:
            st.markdown("### 🔒 Look-Through Earnings (Premium)")
            
            col1, col2 = st.columns([2, 1])
            with col1:
                st.info("**Look-Through Earnings** uses Buffett's 1991 methodology to analyze retained earnings from investees")
                st.markdown("This advanced technique:")
                st.markdown("- Factors in subsidiary earnings")
                st.markdown("- Accounts for ownership percentages")
                st.markdown("- Adjusts for tax implications")
            
            with col2:
                if st.button("🔓 Unlock Look-Through", key="unlock_lookthrough"):
                    st.session_state["show_upgrade_modal"] = True
                    st.rerun()
        
        return False
    
    def check_contrarian_overlay(self, is_premium: bool, show_ui: bool = True) -> bool:
        """Gate contrarian sentiment analysis"""
        if is_premium:
            return True
        
        if show_ui:
            st.markdown("### 🔒 Contrarian Analysis (Premium)")
            
            col1, col2 = st.columns([2, 1])
            with col1:
                st.info("**Contrarian Overlay** factors in market sentiment for contrarian investment opportunities")
                st.markdown("Analyzes:")
                st.markdown("- Fear & Greed Index")
                st.markdown("- Short interest levels")
                st.markdown("- News sentiment")
                st.markdown("- Put/Call ratios")
            
            with col2:
                if st.button("🔓 Unlock Contrarian", key="unlock_contrarian"):
                    st.session_state["show_upgrade_modal"] = True
                    st.rerun()
        
        return False
    
    def check_greenwald_method(self, is_professional: bool, show_ui: bool = True) -> bool:
        """Gate Greenwald maintenance CapEx method"""
        if is_professional:
            return True
        
        if show_ui:
            st.markdown("### 🔒 Greenwald Method (Professional)")
            
            col1, col2 = st.columns([2, 1])
            with col1:
                st.info("**Greenwald PPE/Sales method** provides advanced maintenance CapEx estimation using 5-year historical data")
                st.markdown("This sophisticated approach:")
                st.markdown("- Uses historical PPE/Sales ratios")
                st.markdown("- Separates growth vs. maintenance CapEx")
                st.markdown("- More accurate than simple D&A method")
            
            with col2:
                if st.button("🔓 Unlock Greenwald", key="unlock_greenwald"):
                    st.session_state["show_upgrade_modal"] = True
                    st.rerun()
        
        return False
    
    def check_chatgpt_access(self, user_email: str, is_premium: bool, is_professional: bool, show_ui: bool = True) -> bool:
        """Gate ChatGPT AI analysis"""
        quota_info = self.quota_manager.check_chatgpt_quota(user_email, is_premium, is_professional)
        
        if not quota_info["allowed"]:
            if show_ui:
                if not is_premium:
                    st.markdown("### 🔒 AI Investment Analysis (Premium)")
                    
                    col1, col2 = st.columns([2, 1])
                    with col1:
                        st.info("**AI Analysis** provides ChatGPT-powered insights using Warren Buffett's methodology")
                        st.markdown("Get AI insights on:")
                        st.markdown("- Investment thesis strength")
                        st.markdown("- Risk assessment")
                        st.markdown("- Comparison to Buffett principles")
                        st.markdown("- Strategic recommendations")
                    
                    with col2:
                        if st.button("🔓 Unlock AI Analysis", key="unlock_ai"):
                            st.session_state["show_upgrade_modal"] = True
                            st.rerun()
                else:
                    st.error("🚫 Daily AI analysis limit reached!")
                    
                    col1, col2 = st.columns(2)
                    with col1:
                        st.info(f"**Premium:** {quota_info['used']}/{quota_info['limit']} AI queries used today")
                        st.markdown("*Resets daily*")
                    
                    with col2:
                        if st.button("🏆 Upgrade to Professional", key="upgrade_to_pro"):
                            st.session_state["show_upgrade_modal"] = True
                            st.rerun()
            
            return False
        
        if is_premium and not is_professional and show_ui:
            st.info(f"🤖 **Premium:** {quota_info['remaining']} AI queries remaining today")
        
        return True
    
    def check_pdf_export(self, is_premium: bool, show_ui: bool = True) -> bool:
        """Gate PDF report export"""
        if is_premium:
            return True
        
        if show_ui:
            st.error("🔒 **PDF Export requires Premium subscription**")
            
            col1, col2 = st.columns([2, 1])
            with col1:
                st.info("Generate professional investment analysis reports with:")
                st.markdown("- Complete financial analysis")
                st.markdown("- Risk assessment charts")
                st.markdown("- Buffett score breakdown")
                st.markdown("- Executive summary")
            
            with col2:
                if st.button("🔓 Unlock PDF Reports", key="unlock_pdf"):
                    st.session_state["show_upgrade_modal"] = True
                    st.rerun()
        
        return False
    
    def show_feature_comparison_table(self):
        """Display feature comparison table"""
        st.markdown("### 📊 Plan Comparison")
        
        features_data = [
            ["Company Analyses", "3 per week", "Unlimited", "Unlimited"],
            ["Available Companies", "S&P 500 only", "All public companies", "All public companies"],
            ["Owner Earnings", "✅ Basic", "✅ Full", "✅ Full"],
            ["Circle of Competence", "3 sectors max", "Unlimited", "Unlimited"],
            ["Altman Z-Score", "✅", "✅", "✅"],
            ["Risk Metrics", "❌", "✅ Max DD, Volatility", "✅ All metrics"],
            ["Look-Through Earnings", "❌", "✅", "✅"],
            ["Contrarian Analysis", "❌", "✅", "✅"],
            ["Maintenance CapEx", "D&A method", "D&A method", "✅ Greenwald method"],
            ["AI Analysis", "❌", "5 queries/day", "Unlimited"],
            ["PDF Reports", "❌", "✅", "✅"],
            ["Bulk Analysis", "❌", "❌", "✅ CSV upload"],
            ["API Access", "❌", "❌", "✅"],
            ["Support", "Community", "Email support", "Priority support"],
        ]
        
        df = pd.DataFrame(features_data, columns=[
            "Feature", 
            "🆓 Free", 
            "⭐ Premium ($49/mo)", 
            "🏆 Professional ($149/mo)"
        ])
        
        # Style the dataframe
        st.dataframe(df, use_container_width=True, hide_index=True)
    
    def check_circle_of_competence_limit(self, selected_items: List[str], is_premium: bool) -> bool:
        """Check if user exceeds circle of competence selection limit"""
        if is_premium:
            return True
        
        return len(selected_items) <= 3
    
    def show_usage_dashboard(self, user_email: str):
        """Show user's current usage statistics"""
        usage = self.quota_manager.get_user_usage_summary(user_email)
        
        if not usage:
            return
        
        st.markdown("### 📊 Your Usage")
        
        col1, col2, col3 = st.columns(3)
        
        with col1:
            st.metric(
                "This Week", 
                f"{usage['current_week_analyses']}", 
                f"Analyses completed"
            )
        
        with col2:
            st.metric(
                "Today", 
                f"{usage['current_day_chatgpt']}", 
                f"AI queries used"
            )
        
        with col3:
            st.metric(
                "All Time", 
                f"{usage['total_analyses_ever']}", 
                f"Total analyses"
            )
        
        if usage['recent_analyses']:
            st.markdown("**Recent Analyses:**")
            for analysis in usage['recent_analyses']:
                st.markdown(f"- **{analysis['ticker']}**: {analysis['score']:.1f}/100 ({analysis['date'][:10]})")