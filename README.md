# Buffett Analyzer — Extended (Python + Streamlit)

This app implements Buffett-inspired analysis with **Owner Earnings**, **Altman Z**, **Max Drawdown/Volatility**, **Look-Through Earnings**, a **Circle of Competence** gate, and an optional **Contrarian Sentiment Overlay**. It also exports a **single-company PDF**.

## Quickstart

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
streamlit run app.py
```

Open: http://localhost:8501

## PDF Export
Click **Export Report to PDF** and download the generated file.

## Tests
```bash
pytest
```
