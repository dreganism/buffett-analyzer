# app.py
# Buffett Analyzer — Extended (Python + Streamlit)
# Includes: Circle of Competence, Owner Earnings (+ optional ΔWC), Altman Z/Drawdown/Vol risk,
# Contrarian overlay, Look-Through Earnings, Greenwald Maintenance CapEx with real 5y history
# Author: David Regan (dphackworth)

from yahoo_adapter import (
    fetch_prices_daily,
    fetch_intraday_1m,
    fetch_fundamentals,
    fetch_profile,
    fetch_market_cap,
    fetch_greenwald_history,
    fetch_working_capital_quarterly,
)
import math
import json
from dataclasses import dataclass
from typing import List, Dict, Optional, Tuple

import numpy as np
import pandas as pd
import streamlit as st

from report import export_pdf

# Add this import line after your existing imports
from chatgpt_integration import ChatGPTIntegration, render_chatgpt_modal, add_chatgpt_trigger_button
from openai_client import quick_ping, get_openai_client, _get_api_key  # _get_api_key only if you want to show masked

# -----------------------------
# ---------- GLOSSARY ----------
# -----------------------------
GLOSSARY: Dict[str, str] = {
    "circle_of_competence": "Your 'lane'—businesses and industries you truly understand. Buffett avoids investing outside this circle.",
    "whitelist": "Sectors/industries you explicitly prefer to evaluate. Matching sector OR industry passes the gate.",
    "blacklist": "Sectors/industries to exclude (e.g., pre-revenue biotech, SPACs). Matching entries fail the gate.",
    "complexity_flags": "Quick exclusions for tricky categories like 'pre-revenue', 'binary-fda', 'exploration-only', 'crypto-miner'.",
    "owner_earnings": "Buffett (1986): Owner Earnings ≈ Net Income + Depreciation & Amortization (+ other non-cash) − Maintenance CapEx.",
    "maint_capex_method": "How we estimate maintenance CapEx (the spend needed to sustain current operations).",
    "maint_dep_simple": "Assume Maintenance CapEx ≈ D&A. Simple and conservative when history is limited.",
    "maint_greenwald": "Greenwald PPE/Sales proxy: Maintenance CapEx = Total CapEx − Growth CapEx (estimated from PPE/Sales and sales growth).",
    "weights_section": "Weights for components of the Capital Preservation Score. We normalize internally.",
    "w_z": "Importance of Altman Z (or Z'). Higher Z suggests lower bankruptcy risk.",
    "w_mdd": "Importance of Max Drawdown (inverted). Lower historical drawdown → higher score.",
    "w_vol": "Importance of Annualized Volatility (inverted). Lower volatility → higher score.",
    "weights_autonorm": "Weights auto-normalize so their sum acts like 1.0.",
    "contrarian": "Optional multiplier that slightly boosts score when markets look fearful.",
    "fear_greed": "0–100 composite gauge (lower = fear). Small boost when < 30.",
    "short_interest": "Short interest as fraction of float (e.g., 0.08 = 8%). Small boost at ≥ 8%.",
    "news_sentiment": "Aggregated −1..+1 news sentiment. Small boost when ≤ −0.3.",
    "put_call": "Put/Call ratio (>1 suggests fear). Small boost when > 1.0.",
    "ticker": "Public ticker symbol (e.g., KO, AAPL). Used for prices and fundamentals.",
    "sector": "High-level category (e.g., Consumer Staples). Used by circle-of-competence gate.",
    "industry": "Specific industry (e.g., Beverages – Non-Alcoholic). Also used by the gate.",
    "net_income": "Net income (TTM or last fiscal year).",
    "da": "Depreciation & Amortization—non-cash charges added back in Owner Earnings.",
    "capex_total": "Total capital expenditures (cash outflow for fixed assets).",
    "sales": "Revenue (TTM or last fiscal year).",
    "ppe": "Net Property, Plant & Equipment. Used by the Greenwald estimator.",
    "working_capital": "Current Assets − Current Liabilities. Used in Altman Z.",
    "retained_earnings": "Cumulative profits retained by the company. Used in Altman Z.",
    "ebit": "Earnings Before Interest & Taxes. Used in Altman Z and as operating baseline.",
    "equity_mkt_value": "Market capitalization; for private firms, use book equity.",
    "total_assets": "Total assets on the balance sheet.",
    "total_liabilities": "Total liabilities on the balance sheet.",
    "investee_json": "Optional list for Look-Through Earnings: [{name, ownership_pct (0..1), net_income, dividends_received}].",
    "altman_z": "Altman Z (or Z') combines five ratios to assess bankruptcy risk (Distress/Gray/Safe).",
    "max_drawdown": "Worst peak-to-trough price decline over the period (positive fraction; 0.42 = −42%).",
    "volatility": "Annualized standard deviation of daily returns (10Y).",
    "capital_preservation": "Blend of Z-zone, inverse drawdown, and inverse volatility, weighted by your sliders.",
    "buffett_score": "Illustrative composite blending circle-of-competence, Owner Earnings vs sales, capital preservation, and look-through.",
    "delta_wc": "Change in Working Capital (latest period). Positive increases often represent required reinvestment; optionally subtract from OE.",
}
def H(key: str) -> str:
    return GLOSSARY.get(key, "")

# ------- GPT INTEGRATION -------
def get_current_company_data(ticker: str, oe_final: float, lt: float, z: float, zone: str, 
                           score_cprs: float, buffett_score: float, net_income: float, 
                           sales: float) -> Dict:
    """Compile current company data for ChatGPT context."""
    return {
        "ticker": ticker,
        "net_income": fmt_money_short(net_income),
        "sales": fmt_money_short(sales),
        "owner_earnings": fmt_money_short(oe_final),
        "look_through_earnings": fmt_money_short(lt),
        "altman_z": f"{z:.2f} ({zone})",
        "capital_preservation": f"{score_cprs * 100:.1f}/100",
        "buffett_score": f"{buffett_score:.1f}/100",
        "raw_net_income": net_income,
        "raw_sales": sales,
        "raw_owner_earnings": oe_final,
        "raw_look_through": lt,
        "raw_altman_z": z,
        "raw_capital_preservation": score_cprs,
        "raw_buffett_score": buffett_score
    }

# ------- FORMAT HELPERS -------
def fmt_money_short(value: Optional[float], decimals: int = 1) -> str:
    """Short-scale USD formatter: $1.2K / $3.4M / $5.6B / $1.2T; handles negatives & small numbers."""
    try:
        if value is None or (isinstance(value, float) and math.isnan(value)):
            return "N/A"
        sign = "-" if value < 0 else ""
        v = abs(float(value))
        if v >= 1_000_000_000_000:
            return f"{sign}${v/1_000_000_000_000:.{decimals}f}T"
        if v >= 1_000_000_000:
            return f"{sign}${v/1_000_000_000:.{decimals}f}B"
        if v >= 1_000_000:
            return f"{sign}${v/1_000_000:.{decimals}f}M"
        if v >= 1_000:
            return f"{sign}${v/1_000:.{decimals}f}K"
        return f"{sign}${v:,.0f}"
    except Exception:
        return "N/A"

def fmt_money_price(value: Optional[float]) -> str:
    """Price-style USD: $123.45."""
    try:
        if value is None or (isinstance(value, float) and math.isnan(value)):
            return "N/A"
        return f"${float(value):,.2f}"
    except Exception:
        return "N/A"

def fmt_pct(frac: Optional[float], decimals: int = 1) -> str:
    """Turn 0.1234 -> 12.3%"""
    try:
        if frac is None or (isinstance(frac, float) and math.isnan(frac)):
            return "N/A"
        return f"{float(frac)*100:.{decimals}f}%"
    except Exception:
        return "N/A"

# ---- INPUT WIDGET HELPERS (pretty display under the control) ----
def money_number_input(label: str, key: str, step: float, help: str = "") -> float:
    """Number input for money-like fields."""
    val = st.number_input(label, step=step, key=key, help=help)
    # Removed the user-friendly caption display
    # try:
    #     st.caption(f"{fmt_money_short(val, 2)}  ·  {val:,.0f}")
    # except Exception:
    #     pass
    return val

# ---- Data quality flags (visual) --------------------------------
def render_data_quality_flags():
    """Show gentle warnings when scraped/mapped values look implausible."""
    s = st.session_state
    msgs: List[str] = []

    # PP&E implausibly small vs Sales (e.g., parsing as $10K on a mega-cap)
    try:
        sales_val = float(s.get("inp_sales") or 0.0)
        ppe_val = float(s.get("inp_ppe") or 0.0)
        if sales_val > 1e9 and ppe_val > 0 and ppe_val < 1e-5 * sales_val:
            msgs.append(
                f"**Net PP&E** {fmt_money_short(ppe_val)} looks unusually small relative to "
                f"**Sales** {fmt_money_short(sales_val)} — verify statement mapping/aliases."
            )
    except Exception:
        pass

    # Retained earnings very negative while NI positive (labeling as 'Accumulated deficit' vs RE mixups)
    try:
        re_val = s.get("inp_re", None)
        ni_val = s.get("inp_net_income", None)
        if re_val is not None and ni_val is not None:
            re_val = float(re_val)
            ni_val = float(ni_val)
            if re_val < -1e9 and ni_val > 0:
                msgs.append(
                    "**Retained Earnings** is strongly negative while **Net Income** is positive — "
                    "double-check the 'Retained Earnings (Accumulated Deficit)' line."
                )
    except Exception:
        pass

    if msgs:
        st.warning("Potential data quality issues:")
        # Render as a compact bullet list to avoid odd wrapping
        st.markdown("\n".join([f"- {m}" for m in msgs]))

# -----------------------------
# ---------- UTIL -------------
# -----------------------------
@st.cache_data
def load_prices(ticker: str, years: int = 10) -> pd.Series:
    """Fetch daily prices and return a 1-D float Series (prefer 'Close')."""
    try:
        data = fetch_prices_daily(ticker, years=years)
        
        # Handle case where fetch_prices_daily returns None or empty
        if data is None:
            return pd.Series(dtype=float, name="price")
        
        # Handle case where fetch_prices_daily returns a DataFrame
        if isinstance(data, pd.DataFrame):
            if data.empty:
                return pd.Series(dtype=float, name="price")
            
            if "Close" in data.columns:
                s = data["Close"]
            else:
                # Try to get first numeric column
                num = data.select_dtypes(include=[np.number])
                if not num.empty:
                    s = num.iloc[:, 0]
                else:
                    s = data.iloc[:, 0]
            
            # Ensure s is a Series
            if isinstance(s, pd.DataFrame):
                s = s.iloc[:, 0] if not s.empty else pd.Series(dtype=float)
            
            # Convert to numeric and clean
            s = pd.to_numeric(s, errors="coerce").dropna()
            s.name = "price"
            return s
        
        # Handle case where it's already a Series
        elif isinstance(data, pd.Series):
            if data.empty:
                return pd.Series(dtype=float, name="price")
            
            s = pd.to_numeric(data, errors="coerce").dropna()
            s.name = "price"
            return s
        
        # Handle other cases (list, numpy array, etc.)
        else:
            try:
                # Convert to Series first
                s = pd.Series(data) if not isinstance(data, pd.Series) else data
                s = pd.to_numeric(s, errors="coerce").dropna()
                s.name = "price"
                return s
            except Exception:
                return pd.Series(dtype=float, name="price")
                
    except Exception as e:
        print(f"Error in load_prices for {ticker}: {e}")
        # Return empty Series on any error
        return pd.Series(dtype=float, name="price")

def pct_returns(prices: pd.Series) -> pd.Series:
    """Return simple percentage returns as a Series."""
    if isinstance(prices, pd.DataFrame):
        prices = prices.iloc[:, 0]
    prices = pd.to_numeric(prices, errors="coerce").dropna()
    return prices.pct_change().dropna()

def annualized_vol(returns: pd.Series, trading_days: int = 252) -> float:
    """Annualized volatility as a float."""
    if returns is None or (hasattr(returns, "empty") and returns.empty):
        return float("nan")
    if isinstance(returns, pd.DataFrame):
        returns = returns.iloc[:, 0]
    returns = pd.to_numeric(returns, errors="coerce").dropna()
    if returns.empty:
        return float("nan")
    vol = returns.std(ddof=1) * math.sqrt(trading_days)
    try:
        return float(vol)
    except Exception:
        return float("nan")

def max_drawdown(prices: pd.Series) -> float:
    """Max drawdown as a float (0..1)."""
    if prices is None or (hasattr(prices, "empty") and prices.empty):
        return float("nan")
    if isinstance(prices, pd.DataFrame):
        prices = prices.iloc[:, 0]
    prices = pd.to_numeric(prices, errors="coerce").dropna()
    if prices.empty:
        return float("nan")
    roll_max = prices.cummax()
    drawdowns = (roll_max - prices) / roll_max
    try:
        return float(drawdowns.max())
    except Exception:
        return float("nan")


# -----------------------------
# ---- OWNER EARNINGS ---------
# -----------------------------
@dataclass
class FinancialRow:
    net_income: float
    depreciation_amortization: float
    capex_total: float
    sales: Optional[float] = None
    ppe_net: Optional[float] = None
    other_non_cash: float = 0.0
    delta_working_capital: float = 0.0

def maintenance_capex_simple(dep_amort: float) -> float:
    return max(dep_amort, 0.0)

def maintenance_capex_greenwald_from_hist(
    sales_hist: List[float], ppe_hist: List[float], capex_hist: List[float]
) -> Optional[float]:
    """
    Compute Greenwald maintenance CapEx from actual history:
      - avg_ratio = sum(PPE)/sum(Sales) over N periods (N>=2)
      - growth_capex_t ≈ avg_ratio * max(0, Sales_t - Sales_{t-1})
      - maint_capex_t = CapEx_t − growth_capex_t
    Returns None if insufficient data.
    """
    try:
        if not (sales_hist and ppe_hist and capex_hist):
            return None
        n = min(len(sales_hist), len(ppe_hist), len(capex_hist))
        if n < 2:
            return None
        sales_hist = sales_hist[-n:]
        ppe_hist = ppe_hist[-n:]
        capex_hist = capex_hist[-n:]
        sum_sales = sum(x for x in sales_hist if x is not None)
        sum_ppe = sum(x for x in ppe_hist if x is not None)
        if sum_sales <= 0 or sum_ppe <= 0:
            return None
        avg_ratio = sum_ppe / max(sum_sales, 1e-9)
        sales_t = sales_hist[-1] or 0.0
        sales_prev = sales_hist[-2] or 0.0
        growth_capex = max(avg_ratio * max(0.0, sales_t - sales_prev), 0.0)
        maint = (capex_hist[-1] or 0.0) - growth_capex
        return float(max(maint, 0.0))
    except Exception:
        return None

def maintenance_capex_greenwald(history: List[FinancialRow]) -> float:
    """Legacy variant for tests; keep compatibility."""
    if len(history) < 2:
        return maintenance_capex_simple(history[-1].depreciation_amortization)
    sales = [x.sales for x in history if x.sales is not None]
    ppe = [x.ppe_net for x in history if x.ppe_net is not None]
    if len(sales) < 2 or len(ppe) < 2:
        return maintenance_capex_simple(history[-1].depreciation_amortization)
    avg_ratio = (sum(ppe) / max(sum(sales), 1e-9))
    sales_t = history[-1].sales or 0.0
    sales_prev = history[-2].sales or 0.0
    growth_capex = max(avg_ratio * max(0.0, sales_t - sales_prev), 0.0)
    maint = (history[-1].capex_total or 0.0) - growth_capex
    return max(maint, 0.0)

def owner_earnings(row: FinancialRow, maint_capex: float) -> float:
    """Base Buffett (1986) without ΔWC penalty (kept for tests/backward-compat)."""
    return (
        (row.net_income or 0.0)
        + (row.depreciation_amortization or 0.0)
        + (row.other_non_cash or 0.0)
        - max(maint_capex, 0.0)
    )

def owner_earnings_adjusted(
    base_oe: float,
    delta_wc: float,
    include_wc: bool = True,
    only_increases: bool = True,
) -> float:
    """
    Optionally subtract ΔWC from Owner Earnings.
    If only_increases=True, subtract max(ΔWC, 0).
    """
    if not include_wc:
        return float(base_oe)
    penalty = max(delta_wc, 0.0) if only_increases else float(delta_wc)
    return float(base_oe - penalty)


# -----------------------------
# ---- LOOK-THROUGH EARNINGS ---
# -----------------------------
@dataclass
class InvesteesEarnings:
    name: str
    ownership_pct: float
    net_income: float
    dividends_received: float = 0.0

def look_through_earnings(
    operating_earnings: float,
    investees: List[InvesteesEarnings],
    tax_rate_on_retained: float = 0.21,
) -> float:
    lt = operating_earnings
    for iv in investees:
        retained = max(iv.net_income - iv.dividends_received, 0.0)
        lt += iv.ownership_pct * retained * (1.0 - tax_rate_on_retained)
    return float(lt)


# -----------------------------
# ---- ALTMAN Z & RISK --------
# -----------------------------
def altman_z(
    manufacturing: bool,
    public: bool,
    working_capital: float,
    retained_earnings: float,
    ebit: float,
    equity_mkt_value: float,
    total_assets: float,
    sales: float,
    total_liabilities: float,
) -> Tuple[float, str]:
    eps = 1e-9
    X1 = (working_capital) / max(total_assets, eps)
    X2 = (retained_earnings) / max(total_assets, eps)
    X3 = (ebit) / max(total_assets, eps)
    X4 = (equity_mkt_value if public else max(equity_mkt_value, eps)) / max(total_liabilities, eps)
    X5 = (sales) / max(total_assets, eps)
    if manufacturing and public:
        z = 1.2 * X1 + 1.4 * X2 + 3.3 * X3 + 0.6 * X4 + 1.0 * X5
        zone = "Distress" if z < 1.81 else ("Gray" if z < 2.99 else "Safe")
    else:
        z = 6.56 * X1 + 3.26 * X2 + 6.72 * X3 + 1.05 * X4
        zone = "Distress" if z < 1.1 else ("Gray" if z < 2.6 else "Safe")
    return float(z), zone

def capital_preservation_score(
    z_value: float,
    zone: str,
    mdd: float,
    ann_vol: float,
    w_z: float = 0.5,
    w_mdd: float = 0.3,
    w_vol: float = 0.2,
) -> float:
    base = {"Distress": 0.2, "Gray": 0.6, "Safe": 0.9}.get(zone, 0.5)
    # Defensive float coercion
    try:
        z_val = float(z_value)
    except Exception:
        z_val = 0.0
    z_norm = min(1.0, base * (1.0 + 0.05 * max(z_val, 0.0)))

    # Coerce to float defensively
    try:
        mdd_val = float(mdd)
    except Exception:
        mdd_val = float("nan")
    try:
        vol_val = float(ann_vol)
    except Exception:
        vol_val = float("nan")

    if math.isnan(mdd_val):
        mdd_val = 0.5
    if math.isnan(vol_val):
        vol_val = 0.3

    mdd_norm = max(0.0, 1.0 - min(mdd_val, 0.8))
    vol_norm = max(0.0, 1.0 - min(vol_val, 0.8))
    score = w_z * z_norm + w_mdd * mdd_norm + w_vol * vol_norm
    return float(max(0.0, min(score, 1.0)))


# -----------------------------
# ---- CONTRARIAN OVERLAY ------
# -----------------------------
def contrarian_overlay(sentiment_inputs: Dict[str, Optional[float]]) -> float:
    fg = sentiment_inputs.get("fear_greed_index")
    si = sentiment_inputs.get("short_interest_pct_of_float")
    ns = sentiment_inputs.get("news_sentiment")
    pcr = sentiment_inputs.get("put_call_ratio")
    boost = 1.0
    if fg is not None and fg < 30: boost += 0.05
    if si is not None and si >= 0.08: boost += 0.04
    if ns is not None and ns <= -0.3: boost += 0.03
    if pcr is not None and pcr > 1.0: boost += 0.03
    return float(np.clip(boost, 0.90, 1.15))


# -----------------------------
# ---- CIRCLE OF COMPETENCE ----
# -----------------------------
def circle_of_competence_pass(
    sector: str,
    industry: str,
    whitelist: List[str],
    blacklist: List[str],
    complexity_flags: List[str],
) -> bool:
    s = (sector or "").strip().lower()
    i = (industry or "").strip().lower()
    wl = {x.strip().lower() for x in (whitelist or [])}
    bl = {x.strip().lower() for x in (blacklist or [])}
    flags = {x.strip().lower() for x in (complexity_flags or [])}
    if s in bl or i in bl: return False
    if wl and (s not in wl and i not in wl): return False
    if any(flag in flags for flag in ["pre-revenue", "binary-fda", "exploration-only", "crypto-miner"]): return False
    return True


# -----------------------------
# ---- STATE & CALLBACKS -------
# -----------------------------
DEFAULTS = {
    "inp_ticker": "KO",
    "inp_sector": "Consumer Staples",
    "inp_industry": "Beverages - Non-Alcoholic",
    "inp_net_income": 9500.0,
    "inp_da": 1800.0,
    "inp_capex": 1500.0,
    "inp_sales": 44000.0,
    "inp_ppe": 10000.0,
    "inp_wc": 6000.0,
    "inp_re": 38000.0,
    "inp_ebit": 12000.0,
    "inp_eq_mkt": 260000.0,
    "inp_ta": 95000.0,
    "inp_tl": 52000.0,
    "inp_investee_json": '[{"name":"BottlerCo","ownership_pct":0.25,"net_income":800,"dividends_received":300}]',
    "inp_fg": 50,
    "inp_si": 0.0,
    "inp_ns": 0.0,
    "inp_pcr": 0.9,
    # ΔWC controls
    "inp_include_wc": True,
    "inp_wc_only_inc": True,
    "inp_delta_wc": 0.0,   # auto-filled from last two quarters if available
}

def init_defaults():
    for k, v in DEFAULTS.items():
        if k not in st.session_state:
            st.session_state[k] = v

def fetch_and_fill_from_yahoo():
    """Callback for the Fetch button—safe to mutate session_state before widgets render next run."""
    ticker = st.session_state.get("inp_ticker", "KO")
    prof = fetch_profile(ticker)
    if prof.get("sector"): st.session_state["inp_sector"] = prof["sector"]
    if prof.get("industry"): st.session_state["inp_industry"] = prof["industry"]

    funda = fetch_fundamentals(ticker)

    def _maybe(target_key: str, val):
        if val is None: return
        if isinstance(val, float) and math.isnan(val): return
        st.session_state[target_key] = float(val)

    _maybe("inp_net_income", funda.get("net_income"))
    _maybe("inp_ebit", funda.get("ebit"))
    _maybe("inp_da", funda.get("depreciation"))
    _maybe("inp_capex", funda.get("capex_total"))
    _maybe("inp_sales", funda.get("sales"))
    _maybe("inp_ta", funda.get("total_assets"))
    _maybe("inp_tl", funda.get("total_liabilities"))
    _maybe("inp_re", funda.get("retained_earnings"))
    _maybe("inp_wc", funda.get("working_capital"))
    _maybe("inp_ppe", funda.get("ppe_net"))

    # Δ Working Capital (quarterly latest change)
    wc_series = fetch_working_capital_quarterly(ticker)  # newest last
    if wc_series and len(wc_series) >= 2:
        st.session_state["inp_delta_wc"] = float((wc_series[-1] or 0.0) - (wc_series[-2] or 0.0))

    # Preload Greenwald history for the next render
    gh = fetch_greenwald_history(ticker)
    st.session_state["__greenwald_hist"] = gh  # dict with 'sales', 'ppe_net', 'capex'

    mc = fetch_market_cap(ticker)
    if mc is not None and not (isinstance(mc, float) and math.isnan(mc)):
        st.session_state["inp_eq_mkt"] = float(mc)

    st.session_state["__fetched_ok"] = True  # show toast once


# -----------------------------
# -------- STREAMLIT UI --------
# -----------------------------
def main():
    st.set_page_config(page_title="Buffett Analyzer — Extended", layout="wide")
    init_defaults()  # MUST run before any widgets are created

    # Initialize ChatGPT integration - MOVED INSIDE main()
    if "chatgpt_integration" not in st.session_state:
        st.session_state["chatgpt_integration"] = ChatGPTIntegration()
    
    chat_integration = st.session_state["chatgpt_integration"]

    st.title("Buffett Analyzer")
    # Add ChatGPT trigger button
    add_chatgpt_trigger_button()

    # Show success toast once after a fetch
    if st.session_state.pop("__fetched_ok", False):
        st.success("Auto-filled latest available fundamentals from Yahoo.")

    with st.sidebar:
        st.header("Circle of Competence", help=H("circle_of_competence"))
        user_whitelist = st.multiselect(
            "Whitelisted sectors/industries",
            ["Consumer Staples","Consumer Discretionary","Financials","Healthcare","Industrials","Energy","Utilities","Tech/Platforms","REITs","Materials","Telecom"],
            default=[],
            help=H("whitelist"),
        )
        user_blacklist = st.multiselect(
            "Blacklisted sectors/industries",
            ["Biotech (pre-revenue)","Exploration/Mining","Crypto miners","SPACs","Highly cyclical"],
            default=[],
            help=H("blacklist"),
        )

        st.header("Owner Earnings Settings", help=H("owner_earnings"))
        maint_method = st.radio(
            "Maintenance CapEx method",
            ["≈ Depreciation (simple)", "Greenwald PPE/Sales (5y)"],
            help=H("maint_capex_method"),
        )
        # ΔWC controls
        st.checkbox("Include Δ Working Capital in OE (only increases)", key="inp_include_wc", help=H("delta_wc"))
        st.toggle("ΔWC: penalize only increases (on)", key="inp_wc_only_inc")
        st.caption("If enabled, OE_adj = OE − max(ΔWC, 0).")

        st.header("Risk Weights", help=H("weights_section"))
        w_z = st.slider("Weight: Altman Z", 0.0, 1.0, 0.5, 0.05, help=H("w_z"))
        w_mdd = st.slider("Weight: Max Drawdown (invert)", 0.0, 1.0, 0.3, 0.05, help=H("w_mdd"))
        w_vol = st.slider("Weight: Annualized Volatility (invert)", 0.0, 1.0, 0.2, 0.05, help=H("w_vol"))
        st.caption("Weights auto-normalize in the scoring function.")

        st.header("Contrarian Overlay (optional)", help=H("contrarian"))
        # IMPORTANT: no 'value=' on keyed widgets to avoid Streamlit warning
        st.number_input("Fear & Greed Index (0..100)", min_value=0, max_value=100, key="inp_fg", help=H("fear_greed"))
        st.number_input("Short interest (% of float, e.g., 0.08 = 8%)", min_value=0.0, max_value=1.0, step=0.01, format="%.2f", key="inp_si", help=H("short_interest"))
        st.slider("News sentiment (−1..+1)", -1.0, 1.0, step=0.05, key="inp_ns", help=H("news_sentiment"))
        st.number_input("Put/Call Ratio", min_value=0.0, max_value=5.0, step=0.1, key="inp_pcr", help=H("put_call"))

        with st.expander("Glossary"):
            for k, v in GLOSSARY.items():
                st.markdown(f"- **{k.replace('_',' ').title()}** — {v}")

    colL, colR = st.columns([1.2, 1.0])

    # ---------- Left column ----------
    with colL:
        st.subheader("Inputs")

        # Fetch button BEFORE widgets; on_click updates session_state for next render
        st.button("Fetch fundamentals from Yahoo", on_click=fetch_and_fill_from_yahoo)

        # 🔎 Show quality flags (based on whatever is in session_state now)
        render_data_quality_flags()

        # IMPORTANT: no 'value=' on keyed widgets to let session_state drive values
        ticker = st.text_input("Ticker", key="inp_ticker", help=H("ticker"))
        sector = st.text_input("Sector (manual or from your DB)", key="inp_sector", help=H("sector"))
        industry = st.text_input("Industry (manual or from your DB)", key="inp_industry", help=H("industry"))

        st.markdown("**Financials (TTM or Last FY)**")
        net_income = money_number_input("Net Income", key="inp_net_income", step=100.0, help=H("net_income"))
        da         = money_number_input("Depreciation & Amortization", key="inp_da", step=50.0, help=H("da"))
        capex      = money_number_input("Total CapEx", key="inp_capex", step=50.0, help=H("capex_total"))
        sales      = money_number_input("Sales / Revenue", key="inp_sales", step=100.0, help=H("sales"))
        ppe        = money_number_input("Net PP&E", key="inp_ppe", step=100.0, help=H("ppe"))

        st.markdown("**Balance Sheet (for Z-Score)**")
        wc     = money_number_input("Working Capital", key="inp_wc", step=100.0, help=H("working_capital"))
        re     = money_number_input("Retained Earnings (BS)", key="inp_re", step=100.0, help=H("retained_earnings"))
        ebit   = money_number_input("EBIT", key="inp_ebit", step=100.0, help=H("ebit"))
        eq_mkt = money_number_input("Equity Market Value (or Book Equ., private)", key="inp_eq_mkt", step=1000.0, help=H("equity_mkt_value"))
        ta     = money_number_input("Total Assets", key="inp_ta", step=500.0, help=H("total_assets"))
        tl     = money_number_input("Total Liabilities", key="inp_tl", step=500.0, help=H("total_liabilities"))

        st.markdown("**Investee (Look-Through) — optional**")
        investee_json = st.text_area(
            "Enter list of investees as JSON (name, ownership_pct, net_income, dividends_received)",
            key="inp_investee_json",
            help=H("investee_json"),
        )

    # ---------- Right column ----------
    with colR:
        st.subheader("Process")
        # Circle of Competence PASS/FAIL with color
        inside_coc = circle_of_competence_pass(
            sector, industry,
            whitelist=user_whitelist,
            blacklist=[x.lower() for x in user_blacklist],
            complexity_flags=[x.lower() for x in user_blacklist],
        )
        coc_color = "green" if inside_coc else "red"
        coc_label = f"<span style='color:{coc_color};font-weight:bold'>{'PASS' if inside_coc else 'FAIL'}</span>"
        st.markdown(f"Circle of Competence: {coc_label}", unsafe_allow_html=True)

        # Intraday price (if available)
        intraday = fetch_intraday_1m(ticker)
        if not intraday.empty:
            try:
                last_px = intraday["Close"].dropna().iloc[-1].item()
                st.metric("Latest Price (1m)", fmt_money_price(last_px))
            except Exception:
                pass

        # Maintenance CapEx
        if maint_method.startswith("≈ Dep"):
            maint_capex = maintenance_capex_simple(da)
            maint_help = H("maint_dep_simple")
        else:
            # Real 5y history via Yahoo
            gh = st.session_state.get("__greenwald_hist") or fetch_greenwald_history(ticker)
            maint_g = maintenance_capex_greenwald_from_hist(
                gh.get("sales") or [], gh.get("ppe_net") or [], gh.get("capex") or []
            )
            if maint_g is None:
                # Fallback to simple if insufficient data
                maint_capex = maintenance_capex_simple(da)
                maint_help = H("maint_greenwald") + "  \n*Insufficient history; fell back to ≈ D&A.*"
            else:
                maint_capex = maint_g
                maint_help = H("maint_greenwald")
        st.metric("Maintenance CapEx (est.)", fmt_money_short(maint_capex), help=maint_help)

        # Base Owner Earnings
        row_now = FinancialRow(
            net_income=float(net_income),
            depreciation_amortization=float(da),
            capex_total=float(capex),
            sales=float(sales),
            ppe_net=float(ppe),
        )
        oe_base = owner_earnings(row_now, maint_capex)

        # Δ Working Capital (from Yahoo quarterly; shown & optionally applied)
        delta_wc = float(st.session_state.get("inp_delta_wc", 0.0))
        st.metric("Δ Working Capital (latest qtr)", fmt_money_short(delta_wc), help=H("delta_wc"))

        oe_final = owner_earnings_adjusted(
            base_oe=oe_base,
            delta_wc=delta_wc,
            include_wc=bool(st.session_state.get("inp_include_wc", True)),
            only_increases=bool(st.session_state.get("inp_wc_only_inc", True)),
        )
        st.metric("Owner Earnings (Buffett 1986)", fmt_money_short(oe_final), help=H("owner_earnings"))

        # Look-through earnings
        try:
            investees = [InvesteesEarnings(**d) for d in json.loads(investee_json)]
        except Exception:
            investees = []
        lt = look_through_earnings(operating_earnings=float(ebit), investees=investees)
        st.metric("Look-Through Earnings (Buffett 1991)", fmt_money_short(lt))

        manufacturing = st.toggle("Manufacturing?", value=False)
        public = st.toggle("Public company?", value=True)
        z, zone = altman_z(manufacturing, public, wc, re, ebit, eq_mkt, ta, sales, tl)
        zone_color = {"Safe": "green", "Gray": "orange", "Distress": "red"}.get(zone, "gray")
        zone_label = f"<span style='color:{zone_color};font-weight:bold'>{zone}</span>"
        st.markdown(f"Altman Z: <b>{z:.2f}</b> ({zone_label})", unsafe_allow_html=True)

        prices = load_prices(ticker)
        if not prices.empty:
            mdd = max_drawdown(prices)
            vol = annualized_vol(pct_returns(prices))
        else:
            mdd, vol = float("nan"), float("nan")
        st.metric("Max Drawdown (10y)", fmt_pct(mdd), help=H("max_drawdown"))
        st.metric("Annualized Volatility (10y)", fmt_pct(vol), help=H("volatility"))

        score_cprs = capital_preservation_score(z, zone, mdd, vol, w_z=w_z, w_mdd=w_mdd, w_vol=w_vol)
        st.markdown("**Capital Preservation Score**")
        st.progress(score_cprs)
        st.metric("Capital Preservation Score", f"{score_cprs * 100:.1f}/100", help=H("capital_preservation"))

        mult = contrarian_overlay({
            "fear_greed_index": st.session_state.get("inp_fg", 50),
            "short_interest_pct_of_float": st.session_state.get("inp_si", 0.0),
            "news_sentiment": st.session_state.get("inp_ns", 0.0),
            "put_call_ratio": st.session_state.get("inp_pcr", 0.9),
        })
        st.metric("Contrarian Overlay (multiplier)", f"x{mult:.3f}", help=H("contrarian"))

        oe_ratio = np.clip(oe_final / sales, -1.0, 1.0) if sales > 0 else 0.0
        lt_ratio = np.clip(lt / max(sales, 1e-9), -1.0, 1.0)

        base = (
            0.35 * (1.0 if inside_coc else 0.0)
            + 0.25 * ((oe_ratio + 1) / 2)
            + 0.30 * score_cprs
            + 0.10 * ((lt_ratio + 1) / 2)
        )
        buffett_score = float(np.clip(base * 100.0 * mult, 0.0, 100.0))

        # Buffett Score progress bar
        st.markdown("**Buffett Score**")
        st.progress(buffett_score / 100.0)
        st.success(f"Buffett Score (illustrative): **{buffett_score:.1f}/100**", icon="✅")

        # ---- Buffett Score Breakdown expander ----
        with st.expander("📊 Buffett Score Breakdown"):
            # Fixed top-level blend weights
            w_coc = 0.35
            w_oe  = 0.25
            w_cpr = 0.30
            w_lt  = 0.10

            # Raw 0..1 component scores
            coc_raw = 1.0 if inside_coc else 0.0
            oe_raw  = (oe_ratio + 1) / 2
            cpr_raw = float(score_cprs)
            lt_raw  = (lt_ratio + 1) / 2

            # Weighted components (0..1)
            coc_w = w_coc * coc_raw
            oe_w  = w_oe  * oe_raw
            cpr_w = w_cpr * cpr_raw
            lt_w  = w_lt  * lt_raw

            # Base points and final with multiplier
            base_points = (coc_w + oe_w + cpr_w + lt_w) * 100.0
            final_points = float(np.clip(base_points * mult, 0.0, 100.0))
            contrarian_lift_total = final_points - min(100.0, base_points)

            # Per-component contributions & lifts (in percentage points)
            rows = []
            for name, w, raw, w_contrib in [
                ("Circle of Competence", w_coc, coc_raw, coc_w),
                ("Owner Earnings Ratio", w_oe,  oe_raw,  oe_w),
                ("Capital Preservation",  w_cpr, cpr_raw, cpr_w),
                ("Look-Through Ratio",   w_lt,  lt_raw,  lt_w),
            ]:
                contrib_pts = w_contrib * 100.0
                lift_pts = (mult - 1.0) * contrib_pts  # signed pp added by contrarian
                rows.append({
                    "Component": name,
                    "Raw Weight": f"{w:.2f}",
                    "Raw Score (0–1)": f"{raw:.3f}",
                    "Contribution (pts)": f"{contrib_pts:.2f}",
                    "Contrarian Lift (pp)": f"{lift_pts:+.2f}",
                })

            df_break = pd.DataFrame(rows)
            st.table(df_break)

            st.markdown("---")
            st.write(f"**Base (pre-contrarian):** `{base_points:.2f} / 100`")
            st.write(f"**Contrarian multiplier:** `x{mult:.3f}` → **total lift:** `{contrarian_lift_total:+.2f} pts`")
            st.write(f"**Final Buffett Score:** `{final_points:.2f} / 100`")

            # Optional: Capital Preservation internals
            with st.expander("🔎 Capital Preservation internals (informational)") as _:
                base_zone = {"Distress": 0.2, "Gray": 0.6, "Safe": 0.9}.get(zone, 0.5)
                z_norm_disp = min(1.0, base_zone * (1.0 + 0.05 * max(z, 0.0)))
                mdd_val = mdd if not math.isnan(mdd) else 0.5
                vol_val = vol if not math.isnan(vol) else 0.3
                mdd_norm_disp = max(0.0, 1.0 - min(mdd_val, 0.8))
                vol_norm_disp = max(0.0, 1.0 - min(vol_val, 0.8))
                st.write(f"- **Altman Z normalized:** `{z_norm_disp:.3f}` (zone: {zone}) — weight in CPRS: `{w_z:.2f}`")
                st.write(f"- **(1 − Max Drawdown):** `{mdd_norm_disp:.3f}` — weight in CPRS: `{w_mdd:.2f}`")
                st.write(f"- **(1 − Volatility):** `{vol_norm_disp:.3f}` — weight in CPRS: `{w_vol:.2f}`")
                st.write(f"- **Capital Preservation (0–1):** `{score_cprs:.3f}`")

        # Owner Earnings Ratio progress bar
        st.markdown("**Owner Earnings Ratio (Owner Earnings / Sales)**")
        st.progress((oe_ratio + 1) / 2)
        st.metric("Owner Earnings Ratio", fmt_pct(oe_ratio), help="Owner Earnings as % of Sales")

        # Simple guardrail banner for extreme risk
        if (not math.isnan(mdd) and mdd > 0.7) or (z < 1.1):
            st.warning("Caution: very high drawdown history and/or low Altman Z detected. Investigate solvency/liquidity risk.")

        if st.button("Export Report to PDF"):
            metrics = {
                "Owner Earnings": fmt_money_short(oe_final),
                "Look-Through Earnings": fmt_money_short(lt),
                "Altman Z": f"{z:.2f} ({zone})",
                "Max Drawdown": fmt_pct(mdd),
                "Volatility": fmt_pct(vol),
                "Capital Preservation": f"{score_cprs * 100:.1f}/100",
            }
            pdf_file = export_pdf(f"{ticker}_report.pdf", ticker, buffett_score, metrics)
            st.success(f"Exported to {pdf_file}")
            with open(pdf_file, "rb") as f:
                st.download_button("Download PDF", f, file_name=f"{ticker}_report.pdf", mime="application/pdf")

    # MOVED INSIDE main() - Compile company data for ChatGPT context
    company_data = get_current_company_data(
        ticker=ticker,
        oe_final=oe_final,
        lt=lt,
        z=z,
        zone=zone,
        score_cprs=score_cprs,
        buffett_score=buffett_score,
        net_income=net_income,
        sales=sales
    )

    # MOVED INSIDE main() - Render ChatGPT modal if active
    render_chatgpt_modal(chat_integration, ticker, company_data)

    # MOVED INSIDE main() - Notes caption
    st.caption("""
    **Notes**  
    • Owner Earnings per Buffett (1986): NI + D&A (+non-cash) − Maintenance CapEx (optionally adjust for ΔWC).  
    • Look-Through Earnings per Buffett (1991): add retained earnings of investees pro-rata (after tax).  
    • Capital Preservation blends Altman Z (or Z'), Max Drawdown, and volatility.  
    • Contrarian overlay is optional and user-weighted.  
    • Yahoo fundamentals are best-effort; validate before making decisions.
    """)

if __name__ == "__main__":
    main()