# yahoo_adapter.py
# Reliable Yahoo fetchers for Buffett Analyzer
# Uses yfinance with robust aliasing + fallbacks

from __future__ import annotations
import math
from typing import Dict, List, Optional, Any

import pandas as pd
import yfinance as yf


# -----------------------------
# ---- low-level utilities ----
# -----------------------------
def _as_df(obj) -> pd.DataFrame:
    """Return a DataFrame or an empty DataFrame (avoid boolean checks on DataFrames)."""
    return obj if isinstance(obj, pd.DataFrame) and not obj.empty else pd.DataFrame()


def _latest_from_df(df: pd.DataFrame, row_aliases: List[str]) -> Optional[float]:
    """
    Given a Yahoo-style DF (rows=line items, cols=dates), return the most recent value
    for the first alias that exists. Returns None if not found/empty.
    """
    df = _as_df(df)
    if df.empty:
        return None
    for alias in row_aliases:
        if alias in df.index:
            s = df.loc[alias]
            for v in s:  # columns are newest -> oldest; use first non-null
                if pd.notna(v):
                    try:
                        return float(v)
                    except Exception:
                        pass
    return None


def _series_from_df(df: pd.DataFrame, row_aliases: List[str], max_points: int = 8) -> List[float]:
    """Return list (oldest -> newest) of values for the first alias that exists."""
    df = _as_df(df)
    if df.empty:
        return []
    for alias in row_aliases:
        if alias in df.index:
            s = df.loc[alias]
            vals = [float(v) for v in s[::-1] if pd.notna(v)]  # reverse to oldest -> newest
            if max_points:
                vals = vals[-max_points:]
            return vals
    return []


def _abs_or_none(x: Optional[float]) -> Optional[float]:
    if x is None:
        return None
    try:
        return abs(float(x))
    except Exception:
        return None


def _nan_or(x: Optional[float], default: Optional[float] = None) -> Optional[float]:
    try:
        if x is None:
            return default
        xf = float(x)
        if math.isnan(xf):
            return default
        return xf
    except Exception:
        return default


# -----------------------------
# ---------- API --------------
# -----------------------------
def fetch_prices_daily(ticker: str, years: int = 10) -> pd.Series:
    """Return a 1-D Series of daily Close prices. Handles MultiIndex columns from yfinance."""
    try:
        period = f"{years}y"
        df = yf.download(ticker, period=period, interval="1d", progress=False, auto_adjust=True)
        
        if df is None or df.empty:
            return pd.Series(dtype=float, name="Close")

        # Initialize s as None to track what we extract
        s = None

        # Handle both single-index and MultiIndex columns robustly
        if isinstance(df.columns, pd.MultiIndex):
            # Try the 'Close' panel first
            try:
                close_panel = df.xs("Close", axis=1, level=0, drop_level=False)
            except Exception:
                close_panel = None

            if isinstance(close_panel, pd.DataFrame) and not close_panel.empty:
                # If ticker-level exists, use it; otherwise first column
                try:
                    if ticker in close_panel.columns.get_level_values(-1):
                        s = close_panel.xs(ticker, axis=1, level=-1, drop_level=True)
                    else:
                        s = close_panel.iloc[:, 0]
                except Exception:
                    s = close_panel.iloc[:, 0] if not close_panel.empty else None
            else:
                # Fallback: first numeric column anywhere
                try:
                    num = df.select_dtypes(include=[float, int])
                    s = num.iloc[:, 0] if not num.empty else df.iloc[:, 0]
                except Exception:
                    s = None
        else:
            # Single-level columns
            try:
                if "Close" in df.columns:
                    s = df["Close"]
                else:
                    num = df.select_dtypes(include=[float, int])
                    s = num.iloc[:, 0] if not num.empty else df.iloc[:, 0]
            except Exception:
                s = None

        # Ensure s is a proper Series before processing
        if s is None:
            return pd.Series(dtype=float, name="Close")
        
        # Convert to Series if it's a DataFrame
        if isinstance(s, pd.DataFrame):
            s = s.iloc[:, 0] if not s.empty else pd.Series(dtype=float)
        
        # Ensure it's a pandas Series
        if not isinstance(s, pd.Series):
            try:
                s = pd.Series(s)
            except Exception:
                return pd.Series(dtype=float, name="Close")

        # Convert to numeric and clean
        s = pd.to_numeric(s, errors="coerce").dropna()
        s.name = "Close"
        return s
        
    except Exception as e:
        # Return empty Series on any error
        print(f"Error fetching prices for {ticker}: {e}")
        return pd.Series(dtype=float, name="Close")


def fetch_intraday_1m(ticker: str) -> pd.DataFrame:
    """Return a DataFrame of 1-minute bars for 1 day (empty if not available)."""
    try:
        df = yf.download(ticker, period="1d", interval="1m", progress=False, auto_adjust=True)
        return _as_df(df)
    except Exception:
        return pd.DataFrame()


def fetch_profile(ticker: str) -> Dict[str, Any]:
    """Return {'sector': ..., 'industry': ...} best-effort."""
    try:
        t = yf.Ticker(ticker)
        sector = None
        industry = None
        try:
            info = getattr(t, "info", None) or {}
            if not info:
                info = t.get_info() or {}
            sector = info.get("sector") or info.get("Sector")
            industry = info.get("industry") or info.get("Industry")
        except Exception:
            pass
        return {"sector": sector, "industry": industry}
    except Exception:
        return {"sector": None, "industry": None}


def fetch_market_cap(ticker: str) -> Optional[float]:
    """Return market cap via fast_info or info."""
    try:
        t = yf.Ticker(ticker)
        try:
            mc = t.fast_info.get("market_cap")
            if mc:
                return float(mc)
        except Exception:
            pass
        try:
            info = getattr(t, "info", None) or {}
            if not info:
                info = t.get_info() or {}
            return _nan_or(info.get("marketCap"))
        except Exception:
            return None
    except Exception:
        return None


def fetch_fundamentals(ticker: str) -> Dict[str, Optional[float]]:
    """
    Returns a dict with:
      net_income, ebit, depreciation, capex_total, sales,
      total_assets, total_liabilities, retained_earnings,
      working_capital, ppe_net
    Prefers TTM (sum of last 4 quarters) where appropriate; otherwise latest annual.
    """
    try:
        t = yf.Ticker(ticker)

        # Income & cash flow (quarterly preferred for TTM)
        is_q = _as_df(getattr(t, "quarterly_financials", None))
        cf_q = _as_df(getattr(t, "quarterly_cashflow", None))
        is_a = _as_df(getattr(t, "financials", None))
        cf_a = _as_df(getattr(t, "cashflow", None))

        bs_q = _as_df(getattr(t, "quarterly_balance_sheet", None))
        bs_a = _as_df(getattr(t, "balance_sheet", None))

        def _ttm(df: pd.DataFrame, aliases: List[str]) -> Optional[float]:
            vals = _series_from_df(df, aliases, max_points=4)
            if not vals:
                return None
            return float(sum(vals))

        # TTM fields
        sales = _ttm(is_q, ["Total Revenue", "Operating Revenue", "Revenue"])
        net_income = _ttm(is_q, ["Net Income"])
        ebit = _ttm(is_q, ["Ebit", "EBIT"])
        depreciation = _ttm(cf_q, ["Depreciation And Amortization", "Depreciation", "Amortization"])
        capex_total = _ttm(cf_q, ["Capital Expenditures", "Investments In Property Plant And Equipment"])

        # Fallback to annual if TTM missing
        if sales is None:
            sales = _latest_from_df(is_a, ["Total Revenue", "Operating Revenue", "Revenue"])
        if net_income is None:
            net_income = _latest_from_df(is_a, ["Net Income"])
        if ebit is None:
            ebit = _latest_from_df(is_a, ["Ebit", "EBIT"])
        if depreciation is None:
            depreciation = _latest_from_df(cf_a, ["Depreciation And Amortization", "Depreciation", "Amortization"])
        if capex_total is None:
            capex_total = _latest_from_df(cf_a, ["Capital Expenditures", "Investments In Property Plant And Equipment"])

        # Take absolute CapEx (Yahoo often reports it as negative cash outflow)
        capex_total = _abs_or_none(capex_total)

        # Balance sheet (prefer latest annual snapshot for stock variables)
        total_assets = _latest_from_df(bs_a, ["Total Assets"])
        total_liabilities = _latest_from_df(
            bs_a, ["Total Liab", "Total Liabilities", "Total Liabilities Net Minority Interest"]
        )

        # Net PP&E (with robust aliasing)
        ppe_net = _latest_from_df(
            bs_a,
            [
                "Property Plant Equipment Net",
                "Net Property Plant Equipment",
                "Property, Plant & Equipment Net",
                "Net PPE",
            ],
        )
        # Fallback: Gross PPE - Accumulated Depreciation
        if ppe_net is None:
            gross = _latest_from_df(bs_a, ["Property Plant Equipment", "Gross PPE", "Gross Property Plant And Equipment"])
            acc_dep = _latest_from_df(bs_a, ["Accumulated Depreciation", "Accumulated Depreciation Amortization"])
            if gross is not None and acc_dep is not None:
                try:
                    ppe_net = float(gross) - float(acc_dep)
                except Exception:
                    ppe_net = None

        # Retained Earnings (some feeds label as 'Accumulated Deficit' when negative)
        retained_earnings = _latest_from_df(
            bs_a,
            ["Retained Earnings", "Retained Earnings (Accumulated Deficit)", "Retained earnings"],
        )

        # Working capital (compute for consistency)
        current_assets = _latest_from_df(bs_a, ["Total Current Assets"])
        current_liab = _latest_from_df(bs_a, ["Total Current Liabilities"])
        working_capital = None
        if current_assets is not None and current_liab is not None:
            try:
                working_capital = float(current_assets) - float(current_liab)
            except Exception:
                working_capital = None

        # ---- Sanity checks / clamps ----
        # If PP&E is implausibly tiny vs sales (e.g., $10K for a mega-cap), treat as None.
        if ppe_net is not None and sales is not None:
            try:
                if abs(ppe_net) > 0 and abs(sales) > 0:
                    if abs(ppe_net) < 1e-5 * abs(sales) and abs(sales) > 1e9:
                        ppe_net = None
            except Exception:
                pass

        # If retained earnings still missing, one more direct try
        if retained_earnings is None:
            re_alt = _latest_from_df(bs_a, ["Retained Earnings"])
            retained_earnings = re_alt

        return {
            "net_income": _nan_or(net_income),
            "ebit": _nan_or(ebit),
            "depreciation": _nan_or(depreciation),
            "capex_total": _nan_or(capex_total),
            "sales": _nan_or(sales),
            "total_assets": _nan_or(total_assets),
            "total_liabilities": _nan_or(total_liabilities),
            "retained_earnings": _nan_or(retained_earnings),
            "working_capital": _nan_or(working_capital),
            "ppe_net": _nan_or(ppe_net),
        }
    except Exception as e:
        print(f"Error fetching fundamentals for {ticker}: {e}")
        return {
            "net_income": None,
            "ebit": None,
            "depreciation": None,
            "capex_total": None,
            "sales": None,
            "total_assets": None,
            "total_liabilities": None,
            "retained_earnings": None,
            "working_capital": None,
            "ppe_net": None,
        }


def fetch_greenwald_history(ticker: str) -> Dict[str, List[float]]:
    """
    Returns ~5–8 annual points oldest->newest for:
      sales (revenue), ppe_net, capex
    """
    try:
        t = yf.Ticker(ticker)
        is_a = _as_df(getattr(t, "financials", None))
        cf_a = _as_df(getattr(t, "cashflow", None))
        bs_a = _as_df(getattr(t, "balance_sheet", None))

        sales_hist = _series_from_df(is_a, ["Total Revenue", "Operating Revenue", "Revenue"], max_points=8)

        ppe_hist = _series_from_df(
            bs_a,
            ["Property Plant Equipment Net", "Net Property Plant Equipment", "Property, Plant & Equipment Net", "Net PPE"],
            max_points=8,
        )
        if not ppe_hist:
            gross_series = _series_from_df(bs_a, ["Property Plant Equipment", "Gross Property Plant And Equipment"], max_points=8)
            acc_series = _series_from_df(bs_a, ["Accumulated Depreciation", "Accumulated Depreciation Amortization"], max_points=8)
            if gross_series and acc_series and len(gross_series) == len(acc_series):
                ppe_hist = [g - a for g, a in zip(gross_series, acc_series)]

        capex_hist = _series_from_df(cf_a, ["Capital Expenditures", "Investments In Property Plant And Equipment"], max_points=8)
        capex_hist = [abs(x) for x in capex_hist]  # ensure positive spend

        return {"sales": sales_hist[-5:], "ppe_net": ppe_hist[-5:], "capex": capex_hist[-5:]}
    except Exception as e:
        print(f"Error fetching Greenwald history for {ticker}: {e}")
        return {"sales": [], "ppe_net": [], "capex": []}


def fetch_working_capital_quarterly(ticker: str) -> List[float]:
    """Return list (oldest->newest) of quarterly working capital values."""
    try:
        t = yf.Ticker(ticker)
        bs_q = _as_df(getattr(t, "quarterly_balance_sheet", None))
        ca = _series_from_df(bs_q, ["Total Current Assets"], max_points=12)
        cl = _series_from_df(bs_q, ["Total Current Liabilities"], max_points=12)
        if not ca or not cl:
            return []
        n = min(len(ca), len(cl))
        return [float(ca[i] - cl[i]) for i in range(n)]
    except Exception as e:
        print(f"Error fetching working capital for {ticker}: {e}")
        return []