# India Company Vehicle Tax Calculator (Ather / EV scooter)

Educational estimator for **company-owned Ather-class EV two-wheeler** vs personal purchase under Indian income-tax rules (Rule 15 from Apr 2026 / old Rule 3). Also supports motor-car fixed perquisite rates.

**Not tax advice.** Figures are simplified estimates — consult a CA.

Built for Sahil Kharb / GlomoPay.

## Key rule note

Rule 15 fixed monthly amounts (₹5,000 / ₹7,000 + chauffeur) apply to **motor cars** (including EV *cars*), **not** scooters.

For EV two-wheelers this app uses the “any other vehicle” style estimate:

`taxable perk ≈ max(0, employer running − ₹3,000/mo × 12)` under Rule 15 (₹900/mo under old Rule 3).

## Defaults (Ather-ish)

- Vehicle cost ₹1,75,000 · EV scooter · salary ₹50,00,000
- Annual running/charging ₹24,000 · FY 2026-27 Rule 15 · 5-year horizon

## Run locally

```bash
python3 -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
uvicorn app:app --reload --port 8000
```

## Deploy

Render: `pip install -r requirements.txt` · `uvicorn app:app --host 0.0.0.0 --port $PORT`
