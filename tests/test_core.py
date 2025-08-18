# tests/test_core.py
import math
from app import FinancialRow, owner_earnings, maintenance_capex_simple, capital_preservation_score

def test_owner_earnings_basic():
    row = FinancialRow(net_income=100, depreciation_amortization=50, capex_total=80)
    maint = maintenance_capex_simple(row.depreciation_amortization)
    oe = owner_earnings(row, maint)
    assert math.isclose(oe, 100 + 50 - 50, rel_tol=1e-6)

def test_capital_preservation_score_bounds():
    score = capital_preservation_score(z_value=3.5, zone="Safe", mdd=0.25, ann_vol=0.20)
    assert 0.0 <= score <= 1.0
