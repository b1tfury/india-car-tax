"""India company vehicle tax benefit calculator (educational estimate).

Default scenario: Ather-class EV two-wheeler (scooter), company vs personal buy.
Rule 15 fixed motor-car rates do NOT apply to two-wheelers — see compute().
"""
from __future__ import annotations

import os
from pathlib import Path
from typing import Any, Literal

from fastapi import FastAPI
from fastapi.responses import FileResponse, HTMLResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field

ROOT = Path(__file__).resolve().parent
STATIC = ROOT / "static"

STD_DEDUCTION = 75_000
CESS_RATE = 0.04
SEC_87A_LIMIT = 1_200_000
SEC_87A_REBATE_CAP = 60_000

NEW_REGIME_SLABS: list[tuple[int, float]] = [
    (400_000, 0.00),
    (800_000, 0.05),
    (1_200_000, 0.10),
    (1_600_000, 0.15),
    (2_000_000, 0.20),
    (2_400_000, 0.25),
    (10**15, 0.30),
]

# Motor-car fixed monthly (employer-owned, mixed use, employer pays running)
CAR_RULE15 = {"le_1_6_or_ev": 5_000, "gt_1_6": 7_000, "chauffeur": 3_000}
CAR_RULE3 = {"le_1_6_or_ev": 1_800, "gt_1_6": 2_400, "chauffeur": 900}

# "Any other vehicle" (two-wheeler): employee-owned + employer reimburses →
# taxable = actual expenditure − monthly official deduction (Rule 15 / old Rule 3).
# Used as educational proxy for scooter perquisite when company pays running.
TW_DEDUCT_RULE15 = 3_000  # per month
TW_DEDUCT_RULE3 = 900

app = FastAPI(title="India Company Vehicle Tax Calculator", version="1.1.0")
if STATIC.exists():
    app.mount("/static", StaticFiles(directory=str(STATIC)), name="static")


class CalcRequest(BaseModel):
    car_value: float = Field(
        175_000,
        ge=0,
        description="Cost to company (on-road). Default ~Ather 450X / Rizta-ish EV scooter",
    )
    taxable_salary: float = Field(
        5_000_000,
        ge=0,
        description="Annual taxable salary before standard deduction",
    )
    vehicle_type: Literal["two_wheeler", "motor_car"] = "two_wheeler"
    engine: Literal["le_1_6", "gt_1_6", "electric"] = "electric"
    chauffeur: bool = False
    employer_pays_running: bool = True
    tax_year: Literal["2026-27", "2025-26"] = "2026-27"
    annual_running: float = Field(
        24_000,
        ge=0,
        description="Annual charging / fuel / insurance / service met by employer",
    )
    ownership_years: int = Field(5, ge=1, le=15)
    corp_tax_pct: float = Field(25.17, ge=0, le=50)
    used_180_days: bool = True
    # Advanced: add 10% of vehicle cost as wear for pure-personal-style estimate
    include_wear_tear: bool = False

    @property
    def vehicle_value(self) -> float:
        return self.car_value


def rule_label(tax_year: str) -> str:
    if tax_year == "2026-27":
        return "Rule 15 (FY 2026-27 / Tax Year 2026-27, from 1 Apr 2026)"
    return "Old Rule 3 (FY 2025-26)"


def monthly_car_perquisite(engine: str, chauffeur: bool, tax_year: str) -> int:
    rules = CAR_RULE15 if tax_year == "2026-27" else CAR_RULE3
    base = rules["le_1_6_or_ev"] if engine in ("le_1_6", "electric") else rules["gt_1_6"]
    return base + (rules["chauffeur"] if chauffeur else 0)


def two_wheeler_annual_perk(
    annual_running: float,
    tax_year: str,
    vehicle_value: float,
    include_wear_tear: bool,
    employer_pays_running: bool,
) -> tuple[float, str]:
    """
    Educational estimate for EV scooter / two-wheeler.

    Rule 15 Table II fixed amounts are for *motor cars* (incl. EV cars), not scooters.
    Clearest statutory path for non-car vehicles is employee-owned conveyance where
    employer pays/reimburses expenses: taxable = actual − ₹3,000/mo (Rule 15)
    or ₹900/mo (old Rule 3), subject to prescribed travel records.

    For company-owned scooter we use the same running-expense net-of-deduction
    figure as a practical proxy, and optionally add 10% wear & tear if flagged
    (closer to pure-personal motor-car style valuation — conservative / advanced).
    """
    deduct_mo = TW_DEDUCT_RULE15 if tax_year == "2026-27" else TW_DEDUCT_RULE3
    running = annual_running if employer_pays_running else 0.0
    running_perk = max(0.0, running - deduct_mo * 12)
    wear = 0.1 * vehicle_value if include_wear_tear else 0.0
    total = running_perk + wear
    note = (
        f"Two-wheeler / EV scooter: Rule 15 fixed motor-car rates (₹5,000/₹7,000) do not apply. "
        f"Estimate uses ‘any other vehicle’ style: max(0, employer running ₹{int(running):,} "
        f"− ₹{deduct_mo:,}/mo × 12). "
        + (
            f"Plus optional 10% wear & tear on cost (₹{int(wear):,}) — advanced / conservative."
            if include_wear_tear
            else "Wear & tear on capital not added (default mixed-use proxy). Confirm structure with a CA."
        )
    )
    return total, note


def tax_before_cess(taxable_income: float) -> float:
    if taxable_income <= 0:
        return 0.0
    tax = 0.0
    prev = 0
    remaining = taxable_income
    for upper, rate in NEW_REGIME_SLABS:
        band = min(remaining, upper - prev)
        if band <= 0:
            break
        tax += band * rate
        remaining -= band
        prev = upper
        if remaining <= 0:
            break
    return tax


def income_tax_new_regime(gross_salary_like: float) -> dict[str, float]:
    ti = max(0.0, gross_salary_like - STD_DEDUCTION)
    slab_tax = tax_before_cess(ti)
    rebate = min(slab_tax, SEC_87A_REBATE_CAP) if ti <= SEC_87A_LIMIT else 0.0
    tax_after_rebate = max(0.0, slab_tax - rebate)
    cess = tax_after_rebate * CESS_RATE
    return {
        "taxable_income": ti,
        "slab_tax": slab_tax,
        "rebate_87a": rebate,
        "tax_after_rebate": tax_after_rebate,
        "cess": cess,
        "total_tax": tax_after_rebate + cess,
    }


def marginal_rate_approx(gross_salary_like: float) -> float:
    ti = max(0.0, gross_salary_like - STD_DEDUCTION)
    if ti <= 0:
        return 0.0
    slab = tax_before_cess(ti)
    if ti <= SEC_87A_LIMIT and slab < SEC_87A_REBATE_CAP:
        return 0.0
    rate = 0.30
    for upper, r in NEW_REGIME_SLABS:
        if ti <= upper:
            rate = r
            break
    return rate * (1 + CESS_RATE)


def compute(req: CalcRequest) -> dict[str, Any]:
    rlabel = rule_label(req.tax_year)
    vehicle_value = req.car_value

    if req.vehicle_type == "motor_car":
        monthly = monthly_car_perquisite(req.engine, req.chauffeur, req.tax_year)
        annual_perk = float(monthly * 12)
        perk_note = (
            "Motor car: employer-owned, mixed official + personal, employer pays running — "
            f"fixed monthly perquisite under {rlabel}."
        )
        if not req.employer_pays_running:
            perk_note += (
                " (Toggle says employee pays running — lower fixed rates exist under Rule 15 "
                "₹2,000/₹3,000; this build still shows employer-pays table unless you adjust.)"
            )
        if req.include_wear_tear:
            perk_note += " Pure personal use would be actual expenses + 10% of car cost − recovery (not applied in default)."
    else:
        annual_perk, perk_note = two_wheeler_annual_perk(
            req.annual_running,
            req.tax_year,
            vehicle_value,
            req.include_wear_tear,
            req.employer_pays_running,
        )
        monthly = round(annual_perk / 12)

    tax_without = income_tax_new_regime(req.taxable_salary)
    tax_with = income_tax_new_regime(req.taxable_salary + annual_perk)
    extra_employee_tax = tax_with["total_tax"] - tax_without["total_tax"]

    years = req.ownership_years
    personal_annual_after_tax = vehicle_value / years
    marg = marginal_rate_approx(req.taxable_salary)
    pretax_needed = (
        personal_annual_after_tax / (1 - marg) if marg < 0.999 else personal_annual_after_tax
    )
    net_employee_benefit = personal_annual_after_tax - extra_employee_tax

    corp_rate = req.corp_tax_pct / 100.0
    dep_rate = 0.15 if req.used_180_days else 0.075
    yr1_dep = vehicle_value * dep_rate
    yr1_dep_shield = yr1_dep * corp_rate
    running_shield = req.annual_running * corp_rate if req.annual_running else 0.0

    table: list[dict[str, Any]] = []
    wdv = vehicle_value
    cum_emp_tax = 0.0
    cum_personal = 0.0
    for y in range(1, years + 1):
        rate_y = dep_rate if y == 1 else 0.15
        dep_y = wdv * rate_y
        shield_y = dep_y * corp_rate
        wdv -= dep_y
        emp_tax_y = extra_employee_tax
        personal_y = personal_annual_after_tax
        cum_emp_tax += emp_tax_y
        cum_personal += personal_y
        table.append(
            {
                "year": y,
                "employee_tax_cost": round(emp_tax_y),
                "personal_capital_burden": round(personal_y),
                "company_dep": round(dep_y),
                "company_dep_shield": round(shield_y),
                "wdv_end": round(wdv),
                "cum_employee_tax": round(cum_emp_tax),
                "cum_personal_burden": round(cum_personal),
                "cum_advantage_vs_personal": round(cum_personal - cum_emp_tax),
            }
        )

    engine_label = {
        "le_1_6": "Engine ≤ 1.6L",
        "gt_1_6": "Engine > 1.6L",
        "electric": "Electric (EV)",
    }[req.engine]
    vtype_label = (
        "EV two-wheeler / scooter (e.g. Ather)"
        if req.vehicle_type == "two_wheeler"
        else "Motor car"
    )

    # What-if: if someone applied car EV ₹5k to a scooter
    car_ev_misapply = monthly_car_perquisite("electric", False, req.tax_year) * 12

    return {
        "inputs": {
            "car_value": vehicle_value,
            "vehicle_value": vehicle_value,
            "taxable_salary": req.taxable_salary,
            "vehicle_type": req.vehicle_type,
            "vehicle_type_label": vtype_label,
            "engine": req.engine,
            "engine_label": engine_label,
            "chauffeur": req.chauffeur,
            "employer_pays_running": req.employer_pays_running,
            "tax_year": req.tax_year,
            "rule_label": rlabel,
            "annual_running": req.annual_running,
            "ownership_years": years,
            "corp_tax_pct": req.corp_tax_pct,
            "used_180_days": req.used_180_days,
            "include_wear_tear": req.include_wear_tear,
        },
        "perquisite": {
            "monthly": round(monthly),
            "annual": round(annual_perk),
            "note": perk_note,
            "car_ev_rate_if_misapplied_annual": car_ev_misapply,
            "car_rate_misapply_note": (
                "For reference only: motor-car EV fixed rate would be "
                f"₹{car_ev_misapply:,}/yr — that table is for cars, not scooters."
                if req.vehicle_type == "two_wheeler"
                else None
            ),
        },
        "employee_tax": {
            "without_car": {k: round(v) for k, v in tax_without.items()},
            "with_car": {k: round(v) for k, v in tax_with.items()},
            "extra_tax_due_to_car": round(extra_employee_tax),
            "extra_tax_due_to_perk": round(extra_employee_tax),
            "std_deduction": STD_DEDUCTION,
        },
        "personal_alternative": {
            "annual_after_tax_capital": round(personal_annual_after_tax),
            "approx_marginal_rate_incl_cess": round(marg * 100, 2),
            "pretax_salary_to_fund_annual": round(pretax_needed),
            "horizon_years": years,
        },
        "comparison": {
            "net_employee_benefit_annual": round(net_employee_benefit),
            "explanation": (
                "Net employee benefit ≈ (personal annual after-tax capital cost of buying the "
                "Ather/scooter yourself) − (extra income tax on the company-vehicle perquisite). "
                "Assumes company buys/owns the vehicle; employee does not outlay vehicle cost. "
                "Ignores residual value, interest, GST/ITC nuances, and state EV subsidies."
            ),
        },
        "company": {
            "corp_tax_rate_pct": req.corp_tax_pct,
            "yr1_depreciation": round(yr1_dep),
            "yr1_dep_tax_shield": round(yr1_dep_shield),
            "running_cost_tax_shield": round(running_shield),
            "note": (
                "Depreciation assumed 15% WDV on motor vehicles for business use "
                "(half rate if used <180 days in Yr1) — confirm block with your CA for two-wheelers. "
                "Corporate rate labelled approx (25% + 4% cess; surcharge may vary)."
            ),
        },
        "year_table": table,
        "disclaimer": (
            "Educational estimate only — not tax advice, not a CA opinion. "
            "Rule 15 motor-car fixed perquisites apply to cars (incl. EV cars); "
            "two-wheeler treatment summarised from ‘any other vehicle’ reimbursement rules. "
            "Verify structure and Form 16 reporting with a qualified Chartered Accountant."
        ),
    }


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok"}


@app.post("/api/calculate")
def api_calculate(req: CalcRequest) -> dict[str, Any]:
    return compute(req)


@app.get("/api/defaults")
def api_defaults() -> dict[str, Any]:
    return {
        "vehicle_value": 175_000,
        "taxable_salary": 5_000_000,
        "vehicle_type": "two_wheeler",
        "engine": "electric",
        "annual_running": 24_000,
        "std_deduction": STD_DEDUCTION,
        "tw_deduct_rule15_monthly": TW_DEDUCT_RULE15,
        "tw_deduct_rule3_monthly": TW_DEDUCT_RULE3,
        "car_rule15": CAR_RULE15,
        "car_rule3": CAR_RULE3,
    }


@app.get("/", response_class=HTMLResponse)
def index() -> FileResponse:
    return FileResponse(STATIC / "index.html")


if __name__ == "__main__":
    import uvicorn

    uvicorn.run("app:app", host="0.0.0.0", port=int(os.environ.get("PORT", "8000")), reload=True)
