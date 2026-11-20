import html
import math

import pandas as pd
import streamlit as st

from calc import compute_pay

st.set_page_config(page_title="Ghana Payslip Calculator", page_icon="🧮", layout="wide")

MODE_LABELS = {"Amount": "amt", "% of basic": "pct"}

st.markdown(
    """
<style>
.block-container { padding-top: 2.2rem; padding-bottom: 3rem; max-width: 1180px; }
h1 { letter-spacing: -0.01em; }

/* summary card */
.summary { border-radius: 14px; padding: 18px 20px; background: #1f6b45; color: #fff; }
.summary .label { font-size: .75rem; text-transform: uppercase; letter-spacing: .08em; opacity: .85; }
.summary .net { font-size: 2.1rem; font-weight: 700; line-height: 1.15; margin: 2px 0 12px;
  font-variant-numeric: tabular-nums; overflow-wrap: anywhere; }
.summary .row { display: flex; flex-wrap: wrap; gap: 10px 28px; }
.summary .row div { min-width: 0; }
.summary .row b { display: block; font-size: 1.1rem; font-variant-numeric: tabular-nums; }
.bar { display: flex; height: 8px; border-radius: 99px; overflow: hidden; margin-top: 14px;
  background: rgba(255,255,255,.25); }
.bar i { display: block; height: 100%; }
.legend { display: flex; flex-wrap: wrap; gap: 4px 14px; font-size: .78rem; margin-top: 8px; opacity: .92; }
.legend span::before { content: ""; display: inline-block; width: 9px; height: 9px; border-radius: 2px;
  margin-right: 5px; background: var(--c); vertical-align: -1px; }

/* payslip tables */
.tbl { width: 100%; overflow-x: auto; -webkit-overflow-scrolling: touch; margin-bottom: .6rem; }
.tbl table { width: 100%; border-collapse: collapse; font-size: .92rem; font-variant-numeric: tabular-nums; }
.tbl th { text-align: left; font-size: .72rem; text-transform: uppercase; letter-spacing: .06em;
  opacity: .7; font-weight: 600; padding: 6px 8px 6px 0; border-bottom: 1px solid rgba(128,128,128,.35); }
.tbl td { padding: 7px 8px 7px 0; border-bottom: 1px solid rgba(128,128,128,.2); vertical-align: top; }
.tbl .n { text-align: right; white-space: nowrap; padding-right: 0; padding-left: 10px; }
.tbl tr.total td { font-weight: 700; border-bottom: 0; border-top: 2px solid currentColor; }
.tbl tr.dim td { opacity: .45; }
.tbl small { opacity: .7; }

/* phones */
@media (max-width: 640px) {
  .block-container { padding-top: 1rem; padding-left: 1rem; padding-right: 1rem; }
  h1 { font-size: 1.65rem !important; }
  .summary { padding: 16px; }
  .summary .net { font-size: 1.75rem; }
  .tbl table { font-size: .84rem; }
  .tbl .hide-sm { display: none; }
}
</style>
""",
    unsafe_allow_html=True,
)


def fmt(x: float) -> str:
    return f"GH₵ {x:,.2f}"


def rows_from_editor(df: pd.DataFrame, fallback: str):
    rows = []
    for _, r in df.iterrows():
        value = r.get("Value")
        if value is None or (isinstance(value, float) and math.isnan(value)):
            continue
        name = str(r.get("Name") or "").strip() or fallback
        mode = MODE_LABELS.get(r.get("Type") or "Amount", "amt")
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
            "Name": st.column_config.TextColumn("Name", help=name_hint, width="medium"),
            "Value": st.column_config.NumberColumn("Value", min_value=0.0, step=0.01, format="%.2f", width="small"),
            "Type": st.column_config.SelectboxColumn(
                "Type", options=list(MODE_LABELS), default="Amount", required=True, width="small",
                help="Amount for a fixed GH₵ figure, or % of basic salary",
            ),
        },
    )


def table(headers, rows, total=None):
    """headers: list of (text, is_numeric, hide_on_phone); rows: list of (cells, css_class)."""
    def cell(tag, text, numeric, hide):
        cls = " ".join(c for c in ("n" if numeric else "", "hide-sm" if hide else "") if c)
        return f'<{tag}{f" class={chr(34)}{cls}{chr(34)}" if cls else ""}>{text}</{tag}>'

    head = "".join(cell("th", h, n, s) for h, n, s in headers)
    body = ""
    for cells, css in rows + ([(total, "total")] if total else []):
        body += f'<tr class="{css}">' + "".join(
            cell("td", c, headers[i][1], headers[i][2]) for i, c in enumerate(cells)) + "</tr>"
    st.markdown(f'<div class="tbl"><table><thead><tr>{head}</tr></thead><tbody>{body}</tbody></table></div>',
                unsafe_allow_html=True)


def pct_note(value, mode):
    return f"<br><small>{value:g}% of basic</small>" if mode == "pct" else ""


st.title("Ghana Payslip Calculator")
st.caption("PAYE rates from 1 September 2026 (Act 1178) · SSNIT rates for 2026")

left, right = st.columns([1, 1.1], gap="large")

with left:
    with st.form("pay", border=True):
        st.subheader("Your monthly pay")
        basic = st.number_input("Basic salary (GH₵)", min_value=0.0, value=5000.0, step=100.0, format="%.2f")

        st.markdown("**Allowances**")
        st.caption("One row per allowance. Set Type to **Amount** for a GH₵ figure or **% of basic**.")
        allow_df = editor(
            "allowances",
            [{"Name": "Transport", "Value": 500.0, "Type": "Amount"},
             {"Name": "Housing", "Value": 10.0, "Type": "% of basic"}],
            "e.g. Transport, Housing, Fuel",
        )

        st.markdown("**Deductions**")
        st.caption("SSNIT (5.5%) and PAYE are worked out for you. Add loans, dues or welfare here.")
        ded_df = editor(
            "deductions",
            [{"Name": "Union dues", "Value": 1.0, "Type": "% of basic"},
             {"Name": "Staff loan", "Value": 200.0, "Type": "Amount"}],
            "e.g. Staff loan, Union dues, Welfare",
        )

        st.markdown("**Voluntary Tier 3 pension** (optional)")
        tier3_value = st.number_input("Tier 3 value", min_value=0.0, value=0.0, step=0.5, format="%.2f",
                                      label_visibility="collapsed")
        tier3_type = st.radio("Tier 3 type", list(MODE_LABELS), horizontal=True, label_visibility="collapsed")
        st.caption("Lowers your taxable income, up to 16.5% of basic salary.")

        submitted = st.form_submit_button("Calculate", type="primary", width="stretch")

p = compute_pay(
    basic,
    rows_from_editor(allow_df, "Allowance"),
    rows_from_editor(ded_df, "Deduction"),
    (tier3_value, MODE_LABELS[tier3_type]),
)

with right:
    st.subheader("Your payslip")
    if not submitted:
        st.info("These are example figures. Enter your own pay and press **Calculate**.")

    g = p["gross"] or 1
    parts = [("Net pay", p["net"], "#ffffff"), ("PAYE", p["paye"], "#f2b544"),
             ("SSNIT", p["ssnit"], "#9fd8b8"), ("Other", p["tier3"] + p["other_total"], "#c9d1cc")]
    parts = [x for x in parts if x[1] > 0]
    bar = "".join(f'<i style="width:{max(0, v / g * 100):.2f}%;background:{c}"></i>' for _, v, c in parts)
    legend = "".join(f'<span style="--c:{c}">{n} {v / g * 100:.1f}%</span>' for n, v, c in parts)
    st.markdown(
        f"""<div class="summary">
  <div class="label">Net pay (take-home)</div>
  <div class="net">{fmt(p['net'])}</div>
  <div class="row">
    <div><span class="label">Gross salary</span><b>{fmt(p['gross'])}</b></div>
    <div><span class="label">Total deductions</span><b>{fmt(p['total_deductions'])}</b></div>
  </div>
  <div class="bar">{bar}</div>
  <div class="legend">{legend}</div>
</div>""",
        unsafe_allow_html=True,
    )
    st.write("")

    st.markdown("##### Earnings")
    earn = [(["Basic salary", fmt(p["basic"])], "")]
    earn += [([html.escape(n) + pct_note(v, m), fmt(a)], "") for n, v, m, a in p["allowances"]]
    table([("Item", False, False), ("Amount", True, False)], earn, ["Gross salary", fmt(p["gross"])])

    st.markdown("##### Deductions")
    ssnit_label = "SSNIT, employee 5.5%<br><small>0.5% Tier 1 + 5% Tier 2" + \
        (", capped at GH₵69,000" if p["capped"] else "") + "</small>"
    ded = [([ssnit_label, fmt(p["ssnit"])], ""), (["PAYE income tax", fmt(p["paye"])], "")]
    if p["tier3"] > 0:
        label = "Voluntary Tier 3" + pct_note(p["tier3_value"], p["tier3_mode"])
        if p["tier3_relief"] < p["tier3"]:
            label += f"<br><small>Only {fmt(p['tier3_relief'])} reduces tax</small>"
        ded.append(([label, fmt(p["tier3"])], ""))
    ded += [([html.escape(n) + pct_note(v, m), fmt(a)], "") for n, v, m, a in p["deductions"] if a > 0]
    table([("Item", False, False), ("Amount", True, False)], ded, ["Total deductions", fmt(p["total_deductions"])])

    st.markdown("##### How your PAYE was worked out")
    relief = f" − Tier 3 relief {fmt(p['tier3_relief'])}" if p["tier3_relief"] > 0 else ""
    st.caption(f"Taxable income = gross {fmt(p['gross'])} − SSNIT {fmt(p['ssnit'])}{relief} = **{fmt(p['taxable'])}**")
    band_rows = []
    for r in p["paye_rows"]:
        if math.isinf(r["width"]):
            band = f"Above {r['from']:,.0f}"
        else:
            band = f"{'First' if r['from'] == 0 else 'Next'} {r['width']:,.0f}"
        band_rows.append(([band, f"{r['rate'] * 100:g}%", fmt(r["portion"]), fmt(r["tax"])],
                          "" if r["portion"] > 0 else "dim"))
    table([("Band (GH₵)", False, False), ("Rate", True, False), ("Income in band", True, True), ("Tax", True, False)],
          band_rows, ["Total PAYE", "", "", fmt(p["paye"])])

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
