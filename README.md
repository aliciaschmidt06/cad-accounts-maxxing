# 🍁 Canadian Investment Optimizer

A Flask web app that helps Canadians figure out the best account placement for their investments to maximize after-tax retirement wealth.

## What it does

You tell it what you own and how much. It tells you where to put it (TFSA, RRSP, FHSA, Non-Registered, Real Estate) and projects your after-tax portfolio value over time.

Key rules it enforces:
- **TFSA** lifetime room calculated from your age using CRA annual limits (2009–2025)
- **RRSP** room = 18% of income (max $32,490 for 2025) + any carryforward from prior years
- **FHSA** $8,000/year, $40,000 lifetime — unlocked when you check "First-Time Homebuyer"
- **Non-Registered** capital gains taxed at 50% inclusion rate at your combined federal + provincial marginal rate
- **RRSP** withdrawals taxed as income in retirement (assumed lower bracket)
- **Real Estate** primary residence benefits from the Principal Residence Exemption (tax-free appreciation)
- Over-contribution warnings for TFSA, RRSP, and FHSA

The optimizer places your highest-growth assets in TFSA first (tax-free growth is most valuable on high returns), then FHSA (if eligible), then RRSP (deduction benefit for higher earners), then Non-Registered for overflow. Holdings you manually drag into an account are locked and left alone.

---

## Requirements

- Python 3.9+
- pip

---

## Setup & Run

### 1. Clone / navigate to the project

```bash
cd cad-accounts-maxxing
```

### 2. (Optional but recommended) Create a virtual environment

```bash
python3 -m venv venv
source venv/bin/activate      # macOS / Linux
# venv\Scripts\activate       # Windows
```

### 3. Install Flask

```bash
pip install flask
```

### 4. Run the app

```bash
python3 app.py
```

You should see:

```
 * Running on http://127.0.0.1:5050
```

### 5. Open in your browser

```
http://localhost:5050
```

---

## How to use it

1. **Fill in your profile** — age, income, province, and any existing TFSA/RRSP contributions. Add RRSP carryforward room if you have it (check your CRA MyAccount or last Notice of Assessment).

2. **Add your holdings** — click **Add Holding** for each asset you own. Choose the type (ETF, Stock, Bond, HISA, GIC, Cash, Crypto, Real Estate) and adjust the expected return slider. Defaults are pre-filled with long-run historical averages.

3. **Drag holdings into accounts** *(optional)* — if you already have certain assets in specific accounts and don't want to move them, drag those cards from the Unallocated pool into the appropriate account zone. Those will be locked. Leave anything unallocated if you want the optimizer to decide.

4. **Set your time horizon** — use the "Years to Retirement" slider.

5. **Click Optimize My Portfolio** — the app will:
   - Place all unallocated holdings into optimal accounts
   - Project your after-tax portfolio value year by year
   - Show a growth chart, recommendations table, and personalized insights

---

## Default expected returns

| Asset Type | Default | Notes |
|---|---|---|
| ETF | 7.0% | Broad equity ETF (e.g. XEQT, VEQT) |
| Stock | 8.0% | Individual equities |
| Bond | 3.5% | Bond ETF or individual bonds |
| GIC | 4.0% | Guaranteed Investment Certificate |
| HISA | 2.5% | High-Interest Savings Account |
| Cash | 0.5% | Chequing / savings |
| Crypto | 15.0% | Highly speculative |
| Real Estate | 5.0% | Annual appreciation |

All sliders are adjustable (0–25%).

---

## File structure

```
cad-accounts-maxxing/
├── app.py              # Flask backend — tax rules, optimization, projection logic
└── templates/
    └── index.html      # Single-page UI — Bootstrap 5, SortableJS drag-and-drop, Chart.js
```

---

## ⚠️ Disclaimer

**This is not financial advice. This is not investment advice. This is not tax advice. Do not make financial decisions based on this tool.**

This is a personal learning project built to explore Canadian tax-sheltered account mechanics. It could have bugs, outdated numbers, or outright wrong assumptions. Tax rules change. Contribution limits change. The math might be off.

Treat the output of this tool with the same level of caution you would give if you overheard a drunk uncle talking about stock strategies at a family gathering — interesting to think about, absolutely not something to act on without doing your own research.

Always verify contribution limits, tax rates, and eligibility rules directly with the [CRA website](https://www.canada.ca/en/revenue-agency.html) or a licensed financial advisor before making any investment or tax decisions.
