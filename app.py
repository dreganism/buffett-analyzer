# app.py
# Buffett Analyzer — Extended (Python + Streamlit)
# Includes: Circle of Competence, Owner Earnings, Altman Z/Drawdown/Vol risk, Contrarian overlay, Look-Through Earnings
# Author: David Regan (dphackworth)

from yahoo_adapter import (
    fetch_prices_daily,
    fetch_intraday_1m,
    fetch_fundamentals,
    fetch_profile,
    fetch_market_cap,
)
import math
import json
from dataclasses import dataclass
from typing import List, Dict, Optional

import numpy as np
import pandas as pd
import streamlit as st

from report import export_pdf


# -----------------------------
# ---------- GLOSSARY ----------
# -----------------------------
GLOSSARY: Dict[str, str] = {
    "circle_of_competence": "Your ‘lane’—businesses and industries you truly understand. Buffett avoids investing outside this circle.",
    "whitelist": "Sectors/industries you explicitly prefer to evaluate. Matching sector OR industry passes the gate.",
    "blacklist": "Sectors/industries to exclude (e.g., pre-revenue biotech, SPACs). Matching entries fail the gate.",
    "complexity_flags": "Quick exclusions for tricky categories like 'pre-revenue', 'binary-fda', 'exploration-only', 'crypto-miner'.",
    "owner_earnings": "Buffett (1986): Owner Earnings ≈ Net Income + Depreciation & Amortization (+ other non-cash) − Maintenance CapEx.",
    "maint_capex_method": "How we estimate maintenance CapEx (the spend needed to sustain current operations).",
    "maint_dep_simple": "Assume Maintenance CapEx ≈ D&A. Simple and conservative when history is limited.",
    "maint_greenwald": "Greenwald PPE/Sales proxy: Maintenance CapEx = Total CapEx − Growth CapEx (estimated from PPE/Sales and sales growth).",
    "weights_section": "Weights for components of the Capital Preservation Score. We normalize internally.",
    "w_z": "Importance of Altman Z (or Z’). Higher Z suggests lower bankruptcy risk.",
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
    "altman_z": "Altman Z (or Z’) combines five ratios to assess bankruptcy risk (Distress/Gray/Safe).",
    "max_drawdown": "Worst peak-to-trough price decline over the period (positive fraction; 0.42 = −42%).",
    "volatility": "Annualized standard deviation of daily returns (10Y).",
    "capital_preservation": "Blend of Z-zone, inverse drawdown, and inverse volatility, weighted by your sliders.",
    "buffett_score": "Illustrative composite blending circle-of-competence, Owner Earnings vs sales, capital preservation, and look-through.",
}
def H(key: str) -> str:
    return GLOSSARY.get(key, "")


# -----------------------------
# ---------- UTIL -------------
# -----------------------------
@st.cache_data
def load_prices(ticker: str, years: int = 10) -> pd.Series:
    return fetch_prices_daily(ticker, years=years)

def pct_returns(prices: pd.Series) -> pd.Series:
    return prices.pct_change().dropna()

def annualized_vol(returns: pd.Series, trading_days: int = 252) -> float:
    if returns.empty:
        return float("nan")
    return returns.std(ddof=1) * math.sqrt(trading_days)

def max_drawdown(prices: pd.Series) -> float:
    if prices.empty:
        return float("nan")
    roll_max = prices.cummax()
    drawdowns = (roll_max - prices) / roll_max
    return float(drawdowns.max())


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

def maintenance_capex_greenwald(history: List[FinancialRow]) -> float:
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
    return (
        (row.net_income or 0.0)
        + (row.depreciation_amortization or 0.0)
        + (row.other_non_cash or 0.0)
        - max(maint_capex, 0.0)
    )


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
) -> tuple[float, str]:
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
    z_norm = min(1.0, base * (1.0 + 0.05 * max(z_value, 0.0)))
    mdd_val = mdd if not math.isnan(mdd) else 0.5
    vol_val = ann_vol if not math.isnan(ann_vol) else 0.3
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

    st.title("Buffett Analyzer")

    # Show success toast once after a fetch
    if st.session_state.pop("__fetched_ok", False):
        st.success("Auto-filled latest available fundamentals from Yahoo.")

    with st.sidebar:
        st.header("Circle of Competence", help=H("circle_of_competence"))
        user_whitelist = st.multiselect(
            "Whitelisted sectors/industries",
            ["Consumer Staples","Consumer Discretionary","Financials","Healthcare","Industrials","Energy","Utilities","Tech/Platforms","REITs","Materials","Telecom"],
            [],
            help=H("whitelist"),
        )
        user_blacklist = st.multiselect(
            "Blacklisted sectors/industries",
            ["Biotech (pre-revenue)","Exploration/Mining","Crypto miners","SPACs","Highly cyclical"],
            [],
            help=H("blacklist"),
        )
        st.header("Owner Earnings Settings", help=H("owner_earnings"))
        maint_method = st.radio(
            "Maintenance CapEx method",
            ["≈ Depreciation (simple)", "Greenwald PPE/Sales (5y)"],
            help=H("maint_capex_method"),
        )
        st.header("Risk Weights", help=H("weights_section"))
        w_z = st.slider("Weight: Altman Z", 0.0, 1.0, 0.5, 0.05, help=H("w_z"))
        w_mdd = st.slider("Weight: Max Drawdown (invert)", 0.0, 1.0, 0.3, 0.05, help=H("w_mdd"))
        w_vol = st.slider("Weight: Annualized Volatility (invert)", 0.0, 1.0, 0.2, 0.05, help=H("w_vol"))
        # NOTE: caption() doesn't support help=
        st.caption("Weights auto-normalize in the scoring function.")
        st.header("Contrarian Overlay (optional)", help=H("contrarian"))
        fg = st.number_input("Fear & Greed Index (0..100)", min_value=0, max_value=100, value=st.session_state["inp_fg"], key="inp_fg", help=H("fear_greed"))
        si = st.number_input("Short interest (% of float, e.g., 0.08 = 8%)", min_value=0.0, max_value=1.0, value=st.session_state["inp_si"], step=0.01, format="%.2f", key="inp_si", help=H("short_interest"))
        ns = st.slider("News sentiment (−1..+1)", -1.0, 1.0, st.session_state["inp_ns"], 0.05, key="inp_ns", help=H("news_sentiment"))
        pcr = st.number_input("Put/Call Ratio", min_value=0.0, max_value=5.0, value=st.session_state["inp_pcr"], step=0.1, key="inp_pcr", help=H("put_call"))

        with st.expander("Glossary"):
            for k, v in GLOSSARY.items():
                st.markdown(f"- **{k.replace('_',' ').title()}** — {v}")

    colL, colR = st.columns([1.2, 1.0])

    # ---------- Left column ----------
    with colL:
        st.subheader("Inputs")

        # Fetch button BEFORE widgets; on_click updates session_state for next render
        st.button("Fetch fundamentals from Yahoo", on_click=fetch_and_fill_from_yahoo)

        ticker = st.text_input("Ticker", value=st.session_state["inp_ticker"], key="inp_ticker", help=H("ticker"))
        sector = st.text_input("Sector (manual or from your DB)", value=st.session_state["inp_sector"], key="inp_sector", help=H("sector"))
        industry = st.text_input("Industry (manual or from your DB)", value=st.session_state["inp_industry"], key="inp_industry", help=H("industry"))

        st.markdown("**Financials (TTM or Last FY)**")
        net_income = st.number_input("Net Income", value=st.session_state["inp_net_income"], step=100.0, key="inp_net_income", help=H("net_income"))
        da = st.number_input("Depreciation & Amortization", value=st.session_state["inp_da"], step=50.0, key="inp_da", help=H("da"))
        capex = st.number_input("Total CapEx", value=st.session_state["inp_capex"], step=50.0, key="inp_capex", help=H("capex_total"))
        sales = st.number_input("Sales / Revenue", value=st.session_state["inp_sales"], step=100.0, key="inp_sales", help=H("sales"))
        ppe = st.number_input("Net PP&E", value=st.session_state["inp_ppe"], step=100.0, key="inp_ppe", help=H("ppe"))

        st.markdown("**Balance Sheet (for Z-Score)**")
        wc = st.number_input("Working Capital", value=st.session_state["inp_wc"], step=100.0, key="inp_wc", help=H("working_capital"))
        re = st.number_input("Retained Earnings (BS)", value=st.session_state["inp_re"], step=100.0, key="inp_re", help=H("retained_earnings"))
        ebit = st.number_input("EBIT", value=st.session_state["inp_ebit"], step=100.0, key="inp_ebit", help=H("ebit"))
        eq_mkt = st.number_input("Equity Market Value (or Book Equ., private)", value=st.session_state["inp_eq_mkt"], step=1000.0, key="inp_eq_mkt", help=H("equity_mkt_value"))
        ta = st.number_input("Total Assets", value=st.session_state["inp_ta"], step=500.0, key="inp_ta", help=H("total_assets"))
        tl = st.number_input("Total Liabilities", value=st.session_state["inp_tl"], step=500.0, key="inp_tl", help=H("total_liabilities"))

        st.markdown("**Investee (Look-Through) — optional**")
        investee_json = st.text_area(
            "Enter list of investees as JSON (name, ownership_pct, net_income, dividends_received)",
            value=st.session_state["inp_investee_json"],
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
                last_px = float(intraday["Close"].dropna().iloc[-1])
                st.metric("Latest Price (1m)", f"{last_px:,.2f}")
            except Exception:
                pass

        row_now = FinancialRow(net_income=net_income, depreciation_amortization=da, capex_total=capex, sales=sales, ppe_net=ppe)
        if maint_method.startswith("≈ Dep"):
            maint_capex = maintenance_capex_simple(da)
            maint_help = H("maint_dep_simple")
        else:
            history = [row_now] * 5
            maint_capex = maintenance_capex_greenwald(history)
            maint_help = H("maint_greenwald")
        st.metric("Maintenance CapEx (est.)", f"{maint_capex:,.0f}", help=maint_help)

        oe = owner_earnings(row_now, maint_capex)
        st.metric("Owner Earnings (Buffett 1986)", f"{oe:,.0f}", help=H("owner_earnings"))

        try:
            investees = [InvesteesEarnings(**d) for d in json.loads(investee_json)]
        except Exception:
            investees = []
        lt = look_through_earnings(operating_earnings=float(ebit), investees=investees)
        st.metric("Look-Through Earnings (Buffett 1991)", f"{lt:,.0f}")

        manufacturing = st.toggle("Manufacturing?", value=False)
        public = st.toggle("Public company?", value=True)
        z, zone = altman_z(manufacturing, public, wc, re, ebit, eq_mkt, ta, sales, tl)
        # Altman Z risk zone color
        zone_color = {"Safe": "green", "Gray": "orange", "Distress": "red"}.get(zone, "gray")
        zone_label = f"<span style='color:{zone_color};font-weight:bold'>{zone}</span>"
        st.markdown(f"Altman Z: <b>{z:.2f}</b> ({zone_label})", unsafe_allow_html=True)

        prices = load_prices(ticker)
        if not prices.empty:
            mdd = max_drawdown(prices)
            vol = annualized_vol(pct_returns(prices))
        else:
            mdd, vol = float("nan"), float("nan")
        st.metric("Max Drawdown (10y)", f"{(mdd * 100 if not math.isnan(mdd) else float('nan')):.1f}%", help=H("max_drawdown"))
        st.metric("Annualized Volatility (10y)", f"{(vol * 100 if not math.isnan(vol) else float('nan')):.1f}%", help=H("volatility"))

        score_cprs = capital_preservation_score(z, zone, mdd, vol, w_z=w_z, w_mdd=w_mdd, w_vol=w_vol)
        # Capital Preservation Score progress bar
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

        oe_ratio = np.clip(oe / sales, -1.0, 1.0) if sales > 0 else 0.0
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

        # Owner Earnings Ratio progress bar
        st.markdown("**Owner Earnings Ratio (Owner Earnings / Sales)**")
        st.progress((oe_ratio + 1) / 2)
        st.metric("Owner Earnings Ratio", f"{oe_ratio * 100:.1f}%", help="Owner Earnings as % of Sales")

        if st.button("Export Report to PDF"):
            metrics = {
                "Owner Earnings": f"{oe:,.0f}",
                "Look-Through Earnings": f"{lt:,.0f}",
                "Altman Z": f"{z:.2f} ({zone})",
                "Max Drawdown": f"{(mdd * 100 if not math.isnan(mdd) else float('nan')):.1f}%",
                "Volatility": f"{(vol * 100 if not math.isnan(vol) else float('nan')):.1f}%",
                "Capital Preservation": f"{score_cprs * 100:.1f}/100",
            }
            pdf_file = export_pdf(f"{ticker}_report.pdf", ticker, buffett_score, metrics)
            st.success(f"Exported to {pdf_file}")
            with open(pdf_file, "rb") as f:
                st.download_button("Download PDF", f, file_name=f"{ticker}_report.pdf", mime="application/pdf")

    st.caption("""
**Notes**  
• Owner Earnings per Buffett (1986): NI + D&A (+non-cash) − Maintenance CapEx.  
• Look-Through Earnings per Buffett (1991): add retained earnings of investees pro-rata (after tax).  
• Capital Preservation blends Altman Z (or Z’), Max Drawdown, and volatility.  
• Contrarian overlay is optional and user-weighted.  
• Yahoo fundamentals are best-effort; validate before making decisions.
""")


if __name__ == "__main__":
    main()
