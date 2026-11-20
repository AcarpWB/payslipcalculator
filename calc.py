"""Ghana payslip calculation: PAYE (Act 1178, from 1 Sept 2026) and SSNIT (2026)."""

import math

# Monthly resident PAYE bands: (band width in GH₵, rate)
PAYE_BANDS = [
    (588, 0.0),
    (80, 0.05),
    (100, 0.10),
    (2900, 0.175),
    (16000, 0.25),
    (30332, 0.30),
    (math.inf, 0.35),
]
SSNIT_MAX = 69000.0      # maximum monthly insurable earnings from 1 Jan 2026
EMPLOYEE_RATE = 0.055    # 0.5% to Tier 1 + 5% to Tier 2
EMPLOYER_RATE = 0.13
TIER3_RELIEF_CAP = 0.165  # Tier 3 tax relief limit, share of basic salary


def r2(x: float) -> float:
    return round(x + 0.0, 2)


def to_amount(basic: float, value: float, mode: str) -> float:
    """mode is 'pct' (percentage of basic) or 'amt' (GH₵ amount)."""
    return r2(basic * value / 100 if mode == "pct" else value)


def compute_paye(taxable: float):
    left, lower, total, rows = max(0.0, taxable), 0.0, 0.0, []
    for width, rate in PAYE_BANDS:
        portion = min(left, width)
        left -= portion
        tax = portion * rate
        total += tax
        rows.append({"from": lower, "width": width, "rate": rate, "portion": r2(portion), "tax": r2(tax)})
        lower += width
    return rows, r2(total)


def compute_pay(basic, allowances, deductions=(), tier3=(0.0, "amt")):
    """allowances / deductions: iterables of (name, value, mode)."""
    allow = [(n, v, m, to_amount(basic, v, m)) for n, v, m in allowances]
    other = [(n, v, m, to_amount(basic, v, m)) for n, v, m in deductions]
    gross = r2(basic + sum(a[3] for a in allow))

    insurable = min(basic, SSNIT_MAX)
    ssnit = r2(insurable * EMPLOYEE_RATE)
    tier3_amount = to_amount(basic, *tier3)
    tier3_relief = r2(min(tier3_amount, basic * TIER3_RELIEF_CAP))
    taxable = r2(max(0.0, gross - ssnit - tier3_relief))
    paye_rows, paye = compute_paye(taxable)

    other_total = r2(sum(d[3] for d in other))
    total_ded = r2(ssnit + tier3_amount + paye + other_total)
    employer_ssnit = r2(insurable * EMPLOYER_RATE)
    return {
        "basic": r2(basic), "allowances": allow, "gross": gross,
        "ssnit": ssnit, "capped": basic > SSNIT_MAX,
        "tier3": tier3_amount, "tier3_mode": tier3[1], "tier3_value": tier3[0], "tier3_relief": tier3_relief,
        "taxable": taxable, "paye_rows": paye_rows, "paye": paye,
        "deductions": other, "other_total": other_total,
        "total_deductions": total_ded, "net": r2(gross - total_ded),
        "employer_ssnit": employer_ssnit, "cost_to_company": r2(gross + employer_ssnit),
    }
