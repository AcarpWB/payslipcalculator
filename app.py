import math

import pandas as pd
import streamlit as st

from calc import compute_pay

st.set_page_config(page_title="Ghana Payslip Calculator", page_icon="🧮", layout="wide")

MODE_LABELS = {"GH₵": "amt", "%": "pct"}


def fmt(x: float) -> str:
    return f"GH₵ {x:,.2f}"


def rows_from_editor(df: pd.DataFrame, fallback: str):
    rows = []
    for _, r in df.iterrows():
        value = r.get("Value")
        if value is None or (isinstance(value, float) and math.isnan(value)):
            continue
        name = str(r.get("Name") or "").strip() or fallback
        mode = MODE_LABELS.get(r.get("Type") or "GH₵", "amt")
        rows.append((name, float(value), mode))
    return rows


def editor(key: str, sample: list[dict], name_hint: str):
    return st.data_editor(
        pd.DataFrame(sample, columns=["Name", "Value", "Type"]),
        key=key,
        num_rows="dynamic",
        width="stretch",
        hide_index=True,
        column_config={
            "Name": st.column_config.TextColumn("Name", help=name_hint),
            "Value": st.column_config.NumberColumn("Value", min_value=0.0, step=0.01, format="%.2f"),
            "Type": st.column_config.SelectboxColumn(
                "Type", options=list(MODE_LABELS), default="GH₵", required=True,
                help="GH₵ for a fixed amount, % for a percentage of basic salary",
            ),
        },
    )


st.title("Ghana Payslip Calculator")
st.caption("PAYE rates from 1 September 2026 (Act 1178) · SSNIT rates for 2026")

left, right = st.columns([1, 1.15], gap="large")

with left:
    with st.form("pay"):
        st.subheader("Your monthly pay")
        basic = st.number_input("Basic salary (GH₵)", min_value=0.0, value=5000.0, step=100.0, format="%.2f")

        st.markdown("**Allowances**")
        st.caption("Add a row for each allowance. Choose GH₵ for an amount or % for a percentage of basic salary.")
        allow_df = editor(
            "allowances",
            [{"Name": "Transport", "Value": 500.0, "Type": "GH₵"}, {"Name": "Housing", "Value": 10.0, "Type": "%"}],
            "e.g. Transport, Housing, Fuel",
        )

        st.markdown("**Deductions**")
        st.caption("SSNIT (5.5%) and PAYE are worked out for you. Add any other deductions, such as loans or union dues.")
        ded_df = editor(
            "deductions",
            [{"Name": "Union dues", "Value": 1.0, "Type": "%"}, {"Name": "Staff loan", "Value": 200.0, "Type": "GH₵"}],
            "e.g. Staff loan, Union dues, Welfare",
        )

        st.markdown("**Voluntary Tier 3 pension** (optional)")
        c1, c2 = st.columns([2, 1])
        tier3_value = c1.number_input("Tier 3 value", min_value=0.0, value=0.0, step=0.5, format="%.2f",
                                      label_visibility="collapsed")
        tier3_type = c2.radio("Tier 3 type", list(MODE_LABELS), horizontal=True, label_visibility="collapsed")
        st.caption("Tier 3 lowers your taxable income, up to 16.5% of basic salary.")

        submitted = st.form_submit_button("Calculate", type="primary", width="stretch")

p = compute_pay(
    basic,
    rows_from_editor(allow_df, "Allowance"),
    rows_from_editor(ded_df, "Deduction"),
    (tier3_value, MODE_LABELS[tier3_type]),
)


def pct_note(value, mode):
    return f" ({value:g}% of basic)" if mode == "pct" else ""


with right:
    st.subheader("Your payslip")
    if not submitted:
        st.info("These are example figures. Enter your own pay and press **Calculate**.")

    m1, m2, m3 = st.columns(3)
    m1.metric("Gross salary", fmt(p["gross"]))
    m2.metric("Deductions", fmt(p["total_deductions"]))
    m3.metric("Net pay", fmt(p["net"]))

    st.markdown("##### Earnings")
    earn = [("Basic salary", p["basic"])] + [(n + pct_note(v, m), amt) for n, v, m, amt in p["allowances"]]
    earn.append(("**Gross salary**", p["gross"]))
    st.markdown("| Item | Amount |\n|---|---:|\n" + "\n".join(f"| {n} | {fmt(a)} |" for n, a in earn))

    st.markdown("##### Deductions")
    ssnit_label = "SSNIT, employee 5.5%" + (" (capped at GH₵69,000)" if p["capped"] else "")
    ded = [(ssnit_label, p["ssnit"]), ("PAYE income tax", p["paye"])]
    if p["tier3"] > 0:
        label = "Voluntary Tier 3" + pct_note(p["tier3_value"], p["tier3_mode"])
        if p["tier3_relief"] < p["tier3"]:
            label += f" — only {fmt(p['tier3_relief'])} reduces tax"
        ded.append((label, p["tier3"]))
    ded += [(n + pct_note(v, m), amt) for n, v, m, amt in p["deductions"] if amt > 0]
    ded.append(("**Total deductions**", p["total_deductions"]))
    st.markdown("| Item | Amount |\n|---|---:|\n" + "\n".join(f"| {n} | {fmt(a)} |" for n, a in ded))

    st.markdown("##### How your PAYE was worked out")
    relief = f" − Tier 3 relief {fmt(p['tier3_relief'])}" if p["tier3_relief"] > 0 else ""
    st.caption(f"Taxable income = gross {fmt(p['gross'])} − SSNIT {fmt(p['ssnit'])}{relief} = **{fmt(p['taxable'])}**")
    band_rows = []
    for r in p["paye_rows"]:
        if math.isinf(r["width"]):
            band = f"Above {r['from']:,.0f}"
        else:
            band = f"{'First' if r['from'] == 0 else 'Next'} {r['width']:,.0f}"
        band_rows.append(f"| {band} | {r['rate'] * 100:g}% | {fmt(r['portion'])} | {fmt(r['tax'])} |")
    st.markdown(
        "| Band (GH₵) | Rate | Your income in band | Tax |\n|---|---:|---:|---:|\n"
        + "\n".join(band_rows)
        + f"\n| **Total PAYE** | | | **{fmt(p['paye'])}** |"
    )

    st.success(
        f"Your employer also pays SSNIT at 13% of basic: **{fmt(p['employer_ssnit'])}**. "
        f"This does not come out of your pay. Total cost to the company: **{fmt(p['cost_to_company'])}** a month."
    )

st.divider()
st.caption(
    "**Rates used.** PAYE: monthly resident bands from the Income Tax (Amendment) Act, 2026 (Act 1178), effective "
    "1 September 2026, as published by the [Ghana Revenue Authority](https://gra.gov.gh/domestic-tax/tax-types/paye/). "
    "SSNIT: employee 5.5% and employer 13% of basic salary (Tier 1 13.5%, Tier 2 5%); maximum insurable earnings "
    "GH₵69,000 a month from 1 January 2026. All allowances are treated as taxable cash allowances, and percentages are "
    "worked out on basic salary. Bonus, overtime and non-resident tax are not included. This is an estimate, so check "
    "it against your payslip or with GRA."
)
