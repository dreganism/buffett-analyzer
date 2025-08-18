# yahoo_adapter.py
from __future__ import annotations
import math
from typing import Dict, Optional, Tuple
import pandas as pd
import yfinance as yf

def _latest_non_nan(series: pd.Series) -> Optional[float]:
    if series is None or len(series) == 0:
        return None
    s = series.dropna()
    return None if s.empty else float(s.iloc[0])

def fetch_intraday_1m(ticker: str) -> pd.DataFrame:
    """
    Today’s 1-minute bars (if market is open). Empty DataFrame if unavailable.
    """
    t = yf.Ticker(ticker)
    try:
        df = t.history(period="1d", interval="1m", auto_adjust=False)
        return df if isinstance(df, pd.DataFrame) else pd.DataFrame()
    except Exception:
        return pd.DataFrame()

def fetch_prices_daily(ticker: str, years: int = 10) -> pd.Series:
    """
    Daily prices, robust to Adj Close/Close schema.
    """
    df = yf.download(ticker, period=f"{years}y", interval="1d", progress=False, auto_adjust=False)
    if df is None or len(df) == 0:
        return pd.Series(dtype=float)
    if isinstance(df.columns, pd.MultiIndex):
        # try to find Adj Close or Close in any tuple position
        for name in ("Adj Close", "Close"):
            for col in df.columns:
                parts = col if isinstance(col, tuple) else (col,)
                if any(str(p) == name for p in parts):
                    s = df[col]
                    if isinstance(s, pd.DataFrame):
                        s = s.iloc[:, 0]
                    return s.dropna()
        return pd.Series(dtype=float)
    else:
        if "Adj Close" in df.columns:
            return df["Adj Close"].dropna()
        if "Close" in df.columns:
            return df["Close"].dropna()
        return pd.Series(dtype=float)

def fetch_profile(ticker: str) -> Dict[str, Optional[str]]:
    t = yf.Ticker(ticker)
    sector = industry = None
    try:
        info = t.info or {}
        sector = info.get("sector")
        industry = info.get("industry")
    except Exception:
        pass
    return {"sector": sector, "industry": industry}

def fetch_market_cap(ticker: str) -> Optional[float]:
    t = yf.Ticker(ticker)
    # fast_info is quick and usually reliable
    try:
        mc = getattr(t, "fast_info", None)
        if mc and getattr(mc, "market_cap", None):
            return float(mc.market_cap)
    except Exception:
        pass
    # fallback to info
    try:
        info = t.info or {}
        val = info.get("marketCap")
        return float(val) if val is not None else None
    except Exception:
        return None

def _get_statement_latest(df: Optional[pd.DataFrame], field: str) -> Optional[float]:
    if df is None or df.empty:
        return None
    # yfinance statements are columns = periods (most recent first)
    if field not in df.index:
        return None
    series = df.loc[field]
    series = series.dropna()
    if series.empty:
        return None
    return float(series.iloc[0])

def fetch_fundamentals(ticker: str) -> Dict[str, Optional[float]]:
    """
    Return the minimal set your app needs. Values are 'latest available'.
    Keys:
      net_income, ebit, depreciation, capex_total, sales,
      total_assets, total_liabilities, retained_earnings, working_capital
    """
    t = yf.Ticker(ticker)
    inc = bal = cfs = None
    try:
        inc = t.income_stmt
    except Exception:
        pass
    try:
        bal = t.balance_sheet
    except Exception:
        pass
    try:
        cfs = t.cashflow
    except Exception:
        pass

    # Income statement
    net_income = _get_statement_latest(inc, "Net Income")
    ebit = _get_statement_latest(inc, "EBIT")
    if ebit is None:
        ebit = _get_statement_latest(inc, "Operating Income")
    sales = _get_statement_latest(inc, "Total Revenue")

    # Cash flow
    depreciation = _get_statement_latest(cfs, "Depreciation & Amortization")
    if depreciation is None:
        # some tickers use "Depreciation"
        depreciation = _get_statement_latest(cfs, "Depreciation")
    capex_total = _get_statement_latest(cfs, "Capital Expenditures")
    if capex_total is not None:
        # Yahoo often stores CapEx as negative cash outflow; flip sign to positive spend
        capex_total = -float(capex_total)

    # Balance sheet
    total_assets = _get_statement_latest(bal, "Total Assets")
    total_liabilities = _get_statement_latest(bal, "Total Liabilities Net Minority Interest") \
        or _get_statement_latest(bal, "Total Liabilities")
    retained_earnings = _get_statement_latest(bal, "Retained Earnings")
    current_assets = _get_statement_latest(bal, "Total Current Assets")
    current_liab = _get_statement_latest(bal, "Total Current Liabilities")
    working_capital = None
    if current_assets is not None and current_liab is not None:
        working_capital = float(current_assets) - float(current_liab)

    return {
        "net_income": net_income,
        "ebit": ebit,
        "depreciation": depreciation,
        "capex_total": capex_total,
        "sales": sales,
        "total_assets": total_assets,
        "total_liabilities": total_liabilities,
        "retained_earnings": retained_earnings,
        "working_capital": working_capital,
    }
