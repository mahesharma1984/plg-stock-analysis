#!/usr/bin/env python3
"""
PLG Stock Analysis Dashboard — Streamlit Application

Interactive dashboard for exploring 33 SaaS companies analyzed
using the PLG investment thesis framework.

Usage:
    streamlit run plg_dashboard.py
    streamlit run plg_dashboard.py --server.port 8501

Imports all business logic from plg_core and plg_enhanced_analyzer.
Zero logic duplication — dashboard is purely presentation.
"""

import json
import streamlit as st
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
from dataclasses import asdict
from datetime import datetime
from typing import Dict, List, Optional, Tuple

import plg_core
from plg_core import (
    CompanyData,
    VerdictResult,
    load_company_database,
    build_company_data,
    compute_verdict,
    fetch_yfinance_data,
    _normalize_growth,
    _normalize_retention,
    calculate_confidence_score,
    score_to_confidence_level,
    check_staleness,
    recommend_research,
    _determine_data_tier,
    NDR_ENTRY_THRESHOLD,
    NDR_ELITE_THRESHOLD,
    GROWTH_ENTRY_THRESHOLD,
    GROWTH_ELITE_THRESHOLD,
)

from plg_enhanced_analyzer import (
    PriceData,
    ValuationSignal,
    EnhancedVerdict,
    fetch_enhanced_price_data,
    analyze_valuation,
    compute_enhanced_verdict,
)


# ============================================================
# CONSTANTS & THEME
# ============================================================

VERDICT_COLORS = {
    'STRONG_BUY': '#00C853',
    'BUY': '#4CAF50',
    'WATCH': '#FFC107',
    'SELL': '#F44336',
    'AVOID': '#616161',
}

VERDICT_ORDER = ['STRONG_BUY', 'BUY', 'WATCH', 'SELL', 'AVOID']

VERDICT_EMOJI = {
    'STRONG_BUY': ':star:',
    'BUY': ':large_green_circle:',
    'WATCH': ':large_yellow_circle:',
    'SELL': ':red_circle:',
    'AVOID': ':black_circle:',
}

TIER_COLORS = {
    1: '#1565C0',
    2: '#42A5F5',
    3: '#FFA726',
    4: '#BDBDBD',
}

COMPLETENESS_FIELDS = [
    'ndr', 'gross_retention', 'dbne', 'large_customer_ndr',
    'implied_expansion', 'rpo_growth_yoy', 'revenue_growth_yoy',
    'arr_millions', 'customers_100k_plus', 'customer_growth_yoy',
    'big_tech_threat', 'category_stage', 'switching_cost',
]


# ============================================================
# CACHED DATA LOADERS
# ============================================================

@st.cache_data
def load_database() -> Dict[str, dict]:
    """Load company_database.json (session lifetime)."""
    return load_company_database()


@st.cache_data(ttl=3600)
def compute_all_verdicts(db_json: str) -> Dict[str, dict]:
    """Compute verdicts for all companies using ONLY database data.

    No yfinance calls — this is the "offline" fast path.
    Returns dict: ticker -> {company: dict, verdict: dict}
    """
    db = json.loads(db_json)
    results = {}
    for ticker, info in db.items():
        try:
            company = build_company_data(ticker, info, yf_data={})
            verdict = compute_verdict(company)
            results[ticker] = {
                'company': asdict(company),
                'verdict': asdict(verdict),
            }
        except Exception as e:
            results[ticker] = {
                'company': {'ticker': ticker, 'name': info.get('name', ticker)},
                'verdict': {
                    'ticker': ticker, 'verdict': 'N/A',
                    'confidence': 'N/A', 'confidence_score': 0,
                    'data_tier': 4, 'rationale': f'Error: {e}',
                    'entry_signals_met': 0, 'exit_signals_triggered': 0,
                    'staleness_warning': True, 'stale_fields': [],
                    'missing_signals': [], 'research_recommendations': [],
                },
            }
    return results


@st.cache_data(ttl=900, show_spinner=False)
def fetch_live_data(ticker: str) -> dict:
    """Fetch yfinance data for a single ticker."""
    try:
        return fetch_yfinance_data(ticker)
    except Exception:
        return {}


@st.cache_data(ttl=900, show_spinner=False)
def fetch_price_data_cached(ticker: str) -> dict:
    """Fetch enhanced price/technical data."""
    try:
        pd_result = fetch_enhanced_price_data(ticker)
        return asdict(pd_result) if pd_result else {}
    except Exception:
        return {}


# ============================================================
# HELPERS
# ============================================================

def build_portfolio_dataframe(db: dict, verdicts: dict) -> pd.DataFrame:
    """Convert database + verdicts into a pandas DataFrame."""
    rows = []
    for ticker, info in db.items():
        v = verdicts.get(ticker, {})
        vd = v.get('verdict', {})

        growth_raw = info.get('revenue_growth_yoy')
        growth_pct = _normalize_growth(growth_raw) if growth_raw is not None else None

        rows.append({
            'Ticker': ticker,
            'Name': info.get('name', ticker),
            'Verdict': vd.get('verdict', 'N/A'),
            'Confidence': vd.get('confidence', 'N/A'),
            'Confidence Score': vd.get('confidence_score', 0),
            'Data Tier': vd.get('data_tier', 4),
            'NDR': info.get('ndr'),
            'NDR Tier': info.get('ndr_tier', 4),
            'Growth (%)': growth_pct,
            'Category': info.get('category', 'unknown'),
            'Business Model': info.get('business_model', 'unknown'),
            'Big Tech Threat': info.get('big_tech_threat', 'unknown'),
            'Category Stage': info.get('category_stage', 'unknown'),
            'Switching Cost': info.get('switching_cost', 'unknown'),
            'Entry Signals': vd.get('entry_signals_met', 0),
            'Exit Signals': vd.get('exit_signals_triggered', 0),
            'Staleness': vd.get('staleness_warning', True),
            'Rationale': vd.get('rationale', ''),
            'ARR ($M)': info.get('arr_millions'),
            'Customers 100K+': info.get('customers_100k_plus'),
            'Gross Retention': info.get('gross_retention'),
            'DBNE': info.get('dbne'),
            'Notes': info.get('notes', ''),
        })

    return pd.DataFrame(rows)


def apply_filters(df: pd.DataFrame, filters: dict) -> pd.DataFrame:
    """Apply sidebar filters to the DataFrame."""
    filtered = df.copy()

    if filters.get('verdicts'):
        filtered = filtered[filtered['Verdict'].isin(filters['verdicts'])]
    if filters.get('confidence'):
        filtered = filtered[filtered['Confidence'].isin(filters['confidence'])]
    if filters.get('data_tiers'):
        filtered = filtered[filtered['Data Tier'].isin(filters['data_tiers'])]
    if filters.get('categories'):
        filtered = filtered[filtered['Category'].isin(filters['categories'])]
    if filters.get('stages'):
        filtered = filtered[filtered['Category Stage'].isin(filters['stages'])]
    if filters.get('threats'):
        filtered = filtered[filtered['Big Tech Threat'].isin(filters['threats'])]

    return filtered


def score_dimension(value, scale_map: dict, default: int = 0) -> int:
    """Score a qualitative dimension 0-3 using a mapping."""
    if value is None:
        return default
    return scale_map.get(value, default)


def verdict_color_bg(verdict: str) -> str:
    """Return a light background color for a verdict."""
    return {
        'STRONG_BUY': '#C8E6C9',
        'BUY': '#E8F5E9',
        'WATCH': '#FFF9C4',
        'SELL': '#FFCDD2',
        'AVOID': '#E0E0E0',
    }.get(verdict, '#FFFFFF')


def fmt_pct(val, decimals=0) -> str:
    """Format a value as percentage string."""
    if val is None:
        return "N/A"
    return f"{val:.{decimals}f}%"


def fmt_currency(val) -> str:
    """Format market cap."""
    if val is None:
        return "N/A"
    if val >= 1e9:
        return f"${val / 1e9:.1f}B"
    return f"${val / 1e6:.0f}M"


# ============================================================
# SIDEBAR
# ============================================================

def render_sidebar(db: dict, df: pd.DataFrame) -> Tuple[str, dict]:
    """Render sidebar: navigation + filters. Returns (view_name, filters_dict)."""

    st.sidebar.title("PLG Stock Analysis")
    st.sidebar.caption("Thesis-Based Investment Dashboard")
    st.sidebar.markdown("---")

    # Navigation
    nav = st.sidebar.radio(
        "View",
        ["Portfolio Overview", "Company Deep Dive", "Screening", "Data Quality"],
        index=0,
    )

    st.sidebar.markdown("---")
    st.sidebar.subheader("Filters")

    filters = {}

    filters['verdicts'] = st.sidebar.multiselect(
        "Verdict",
        options=VERDICT_ORDER,
        default=VERDICT_ORDER,
    )

    filters['confidence'] = st.sidebar.multiselect(
        "Confidence",
        options=['HIGH', 'MEDIUM', 'LOW', 'INSUFFICIENT'],
        default=['HIGH', 'MEDIUM', 'LOW', 'INSUFFICIENT'],
    )

    filters['data_tiers'] = st.sidebar.multiselect(
        "Data Tier",
        options=[1, 2, 3, 4],
        default=[1, 2, 3, 4],
        format_func=lambda x: f"Tier {x}",
    )

    all_categories = sorted(df['Category'].unique())
    filters['categories'] = st.sidebar.multiselect(
        "Category",
        options=all_categories,
        default=all_categories,
    )

    all_stages = sorted(df['Category Stage'].unique())
    filters['stages'] = st.sidebar.multiselect(
        "Category Stage",
        options=all_stages,
        default=all_stages,
    )

    all_threats = sorted(df['Big Tech Threat'].unique())
    filters['threats'] = st.sidebar.multiselect(
        "Big Tech Threat",
        options=all_threats,
        default=all_threats,
    )

    # Company selector for Deep Dive
    if nav == "Company Deep Dive":
        st.sidebar.markdown("---")
        ticker_list = sorted(db.keys())
        filters['selected_ticker'] = st.sidebar.selectbox(
            "Select Company",
            options=ticker_list,
            format_func=lambda t: f"{t} — {db[t].get('name', t)}",
        )

    st.sidebar.markdown("---")
    st.sidebar.caption(f"Database: {len(db)} companies")

    return nav, filters


# ============================================================
# VIEW 1: PORTFOLIO OVERVIEW
# ============================================================

def render_portfolio_overview(df: pd.DataFrame, verdicts: dict):
    """Main landing page with summary metrics, charts, and company table."""

    st.header("Portfolio Overview")

    # --- Summary Metrics ---
    total = len(df)
    buy_count = len(df[df['Verdict'].isin(['STRONG_BUY', 'BUY'])])
    avg_conf = df['Confidence Score'].mean() if total > 0 else 0
    stale_count = len(df[df['Staleness'] == True])

    col1, col2, col3, col4 = st.columns(4)
    col1.metric("Companies", total)
    col2.metric("Strong Buy / Buy", buy_count)
    col3.metric("Avg Confidence", f"{avg_conf:.0%}")
    col4.metric("Stale Data Alerts", stale_count)

    st.markdown("---")

    # --- Charts Row ---
    chart_left, chart_right = st.columns(2)

    with chart_left:
        verdict_counts = df['Verdict'].value_counts().reindex(VERDICT_ORDER).fillna(0).astype(int)
        fig_verdict = px.pie(
            names=verdict_counts.index,
            values=verdict_counts.values,
            color=verdict_counts.index,
            color_discrete_map=VERDICT_COLORS,
            title="Verdict Distribution",
        )
        fig_verdict.update_traces(textposition='inside', textinfo='value+label')
        fig_verdict.update_layout(showlegend=False, margin=dict(t=40, b=0, l=0, r=0))
        st.plotly_chart(fig_verdict, use_container_width=True)

    with chart_right:
        tier_counts = df['Data Tier'].value_counts().sort_index()
        tier_labels = [f"Tier {t}" for t in tier_counts.index]
        tier_color_list = [TIER_COLORS.get(t, '#999') for t in tier_counts.index]
        fig_tier = px.bar(
            x=tier_counts.values,
            y=tier_labels,
            orientation='h',
            title="Data Tier Distribution",
            labels={'x': 'Companies', 'y': ''},
            color=tier_labels,
            color_discrete_sequence=tier_color_list,
        )
        fig_tier.update_layout(showlegend=False, margin=dict(t=40, b=0, l=0, r=0))
        st.plotly_chart(fig_tier, use_container_width=True)

    st.markdown("---")

    # --- Company Table ---
    display_df = df[[
        'Ticker', 'Name', 'Verdict', 'Confidence', 'Confidence Score',
        'Data Tier', 'NDR', 'Growth (%)', 'Category Stage',
        'Big Tech Threat', 'Entry Signals', 'Exit Signals', 'Staleness',
    ]].copy()

    display_df['NDR'] = display_df['NDR'].apply(lambda x: f"{x:.0f}%" if pd.notna(x) else "N/A")
    display_df['Growth (%)'] = display_df['Growth (%)'].apply(lambda x: f"{x:.0f}%" if pd.notna(x) else "N/A")
    display_df['Confidence Score'] = display_df['Confidence Score'].apply(lambda x: f"{x:.0%}")
    display_df['Entry Signals'] = display_df['Entry Signals'].apply(lambda x: f"{x}/5")
    display_df['Exit Signals'] = display_df['Exit Signals'].apply(lambda x: str(x))
    display_df['Data Tier'] = display_df['Data Tier'].apply(lambda x: f"T{x}")
    display_df['Staleness'] = display_df['Staleness'].apply(lambda x: "Yes" if x else "No")

    # Sort by verdict priority
    verdict_sort = {v: i for i, v in enumerate(VERDICT_ORDER)}
    display_df['_sort'] = display_df['Verdict'].map(verdict_sort).fillna(99)
    display_df = display_df.sort_values('_sort').drop(columns=['_sort'])

    st.dataframe(
        display_df,
        use_container_width=True,
        height=min(35 * len(display_df) + 38, 800),
        hide_index=True,
        column_config={
            'Ticker': st.column_config.TextColumn('Ticker', width='small'),
            'Name': st.column_config.TextColumn('Name', width='medium'),
            'Verdict': st.column_config.TextColumn('Verdict', width='small'),
            'Confidence': st.column_config.TextColumn('Conf.', width='small'),
            'Confidence Score': st.column_config.TextColumn('Score', width='small'),
            'Data Tier': st.column_config.TextColumn('Tier', width='small'),
            'NDR': st.column_config.TextColumn('NDR', width='small'),
            'Growth (%)': st.column_config.TextColumn('Growth', width='small'),
            'Category Stage': st.column_config.TextColumn('Stage', width='small'),
            'Big Tech Threat': st.column_config.TextColumn('BT Threat', width='small'),
            'Entry Signals': st.column_config.TextColumn('Entry', width='small'),
            'Exit Signals': st.column_config.TextColumn('Exit', width='small'),
            'Staleness': st.column_config.TextColumn('Stale', width='small'),
        },
    )

    st.caption("Select **Company Deep Dive** in the sidebar to see full analysis for any company.")


# ============================================================
# VIEW 2: COMPANY DEEP DIVE
# ============================================================

def render_company_deep_dive(db: dict, verdicts: dict, ticker: Optional[str]):
    """Detailed analysis for a single company."""

    if not ticker:
        st.info("Select a company from the sidebar to view detailed analysis.")
        return

    info = db.get(ticker, {})
    v = verdicts.get(ticker, {})
    vd = v.get('verdict', {})

    # --- Header ---
    st.header(f"{ticker} — {info.get('name', ticker)}")
    cat = info.get('category', 'unknown').replace('_', ' ').title()
    bm = info.get('business_model', 'unknown').replace('_', ' ').title()
    st.caption(f"Category: {cat}  |  Model: {bm}")

    # --- Verdict Banner ---
    verdict = vd.get('verdict', 'N/A')
    confidence = vd.get('confidence', 'N/A')
    conf_score = vd.get('confidence_score', 0)
    tier = vd.get('data_tier', 4)

    banner_text = f"**{verdict}**  |  Confidence: {confidence} ({conf_score:.0%})  |  Data Tier: {tier}"
    if verdict in ('STRONG_BUY', 'BUY'):
        st.success(banner_text)
    elif verdict == 'WATCH':
        st.warning(banner_text)
    elif verdict in ('SELL', 'AVOID'):
        st.error(banner_text)
    else:
        st.info(banner_text)

    # --- Key Metrics Row ---
    ndr = info.get('ndr')
    growth_raw = info.get('revenue_growth_yoy')
    growth = _normalize_growth(growth_raw) if growth_raw is not None else None

    mcol1, mcol2, mcol3, mcol4, mcol5, mcol6 = st.columns(6)
    mcol1.metric("NDR", fmt_pct(ndr))
    mcol2.metric("Revenue Growth", fmt_pct(growth))
    mcol3.metric("ARR", f"${info.get('arr_millions', 'N/A')}M" if info.get('arr_millions') else "N/A")
    mcol4.metric("Customers 100K+", info.get('customers_100k_plus', 'N/A'))
    mcol5.metric("Switching Cost", (info.get('switching_cost', 'unknown') or 'unknown').title())
    mcol6.metric("NDR Tier", f"Tier {info.get('ndr_tier', 4)}")

    st.markdown("---")

    # --- Rationale ---
    st.subheader("Verdict Rationale")
    st.info(vd.get('rationale', 'No rationale available.'))

    # --- Signal Breakdown ---
    st.subheader("Signal Breakdown")
    sig_left, sig_right = st.columns(2)

    with sig_left:
        entry = vd.get('entry_signals_met', 0)
        st.markdown(f"**Entry Signals: {entry}/5**")
        st.progress(min(entry / 5.0, 1.0))

    with sig_right:
        exit_sig = vd.get('exit_signals_triggered', 0)
        st.markdown(f"**Exit Signals: {exit_sig}**")
        if exit_sig > 0:
            st.progress(min(exit_sig / 4.0, 1.0))
        else:
            st.progress(0.0)
            st.caption("No exit signals triggered")

    missing = vd.get('missing_signals', [])
    if missing:
        st.caption(f"Missing signals: {', '.join(missing)}")

    st.markdown("---")

    # --- Competitive Assessment Radar ---
    st.subheader("Competitive Assessment")

    # Score dimensions 0-3
    ndr_score = 0
    if ndr is not None:
        if ndr >= 120:
            ndr_score = 3
        elif ndr >= 110:
            ndr_score = 2
        elif ndr > 0:
            ndr_score = 1

    growth_score = 0
    if growth is not None:
        if growth >= 30:
            growth_score = 3
        elif growth >= 20:
            growth_score = 2
        elif growth > 0:
            growth_score = 1

    bt_map = {'low': 3, 'medium': 2, 'medium_high': 1, 'high': 0, 'very_high': 0, 'unknown': 0}
    bt_score = bt_map.get(info.get('big_tech_threat', 'unknown'), 0)

    switch_map = {'high': 3, 'medium': 2, 'low': 1, 'unknown': 0}
    switch_score = switch_map.get(info.get('switching_cost', 'unknown'), 0)

    cat_map = {'emerging': 3, 'early_growth': 3, 'mid_growth': 2, 'mature': 1, 'commoditizing': 0, 'unknown': 0}
    cat_score = cat_map.get(info.get('category_stage', 'unknown'), 0)

    dimensions = ['NDR Strength', 'Growth', 'Big Tech Shield', 'Switching Cost', 'Category Position']
    scores = [ndr_score, growth_score, bt_score, switch_score, cat_score]

    fig_radar = go.Figure(data=go.Scatterpolar(
        r=scores + [scores[0]],  # close the polygon
        theta=dimensions + [dimensions[0]],
        fill='toself',
        fillcolor='rgba(76, 175, 80, 0.2)',
        line=dict(color='#4CAF50', width=2),
        name=ticker,
    ))
    fig_radar.update_layout(
        polar=dict(
            radialaxis=dict(visible=True, range=[0, 3], tickvals=[0, 1, 2, 3]),
        ),
        showlegend=False,
        margin=dict(t=20, b=20, l=60, r=60),
        height=350,
    )
    st.plotly_chart(fig_radar, use_container_width=True)

    comp_left, comp_right = st.columns(2)
    with comp_left:
        st.markdown(f"**Big Tech Threat:** {info.get('big_tech_threat', 'unknown')}")
        st.markdown(f"**Category Stage:** {info.get('category_stage', 'unknown')}")
    with comp_right:
        st.markdown(f"**Switching Cost:** {info.get('switching_cost', 'unknown')}")
        st.markdown(f"**Big Tech Announced:** {'Yes' if info.get('big_tech_announced') else 'No'}")

    st.markdown("---")

    # --- Live Price & Valuation (fetched on demand) ---
    st.subheader("Price & Valuation (Live)")
    with st.spinner(f"Fetching live market data for {ticker}..."):
        yf_data = fetch_live_data(ticker)
        price_dict = fetch_price_data_cached(ticker)

    live_ok = bool(yf_data.get('current_price') or price_dict.get('current_price'))

    if live_ok:
        price = price_dict.get('current_price') or yf_data.get('current_price')
        mkt_cap = yf_data.get('market_cap')
        ps = price_dict.get('price_to_sales')
        rsi = price_dict.get('rsi_14')
        w52_high = price_dict.get('week_52_high')
        w52_low = price_dict.get('week_52_low')
        off_high = price_dict.get('pct_off_high')
        ytd_ret = price_dict.get('ytd_return')
        ret_3m = price_dict.get('return_3m')
        sma50 = price_dict.get('sma_50')
        sma200 = price_dict.get('sma_200')

        p1, p2, p3, p4 = st.columns(4)
        p1.metric("Price", f"${price:.2f}" if price else "N/A")
        p2.metric("Market Cap", fmt_currency(mkt_cap))
        p3.metric("P/S Ratio", f"{ps:.1f}x" if ps else "N/A")
        p4.metric("RSI (14)", f"{rsi:.0f}" if rsi else "N/A")

        p5, p6, p7, p8 = st.columns(4)
        p5.metric("52W High", f"${w52_high:.2f}" if w52_high else "N/A")
        p6.metric("52W Low", f"${w52_low:.2f}" if w52_low else "N/A")
        p7.metric("vs 52W High", fmt_pct(off_high, 1))
        p8.metric("YTD Return", fmt_pct(ytd_ret, 1))

        p9, p10, p11, p12 = st.columns(4)
        p9.metric("3M Return", fmt_pct(ret_3m, 1))
        p10.metric("SMA 50", f"${sma50:.2f}" if sma50 else "N/A")
        p11.metric("SMA 200", f"${sma200:.2f}" if sma200 else "N/A")
        p12.metric("Gross Margin", fmt_pct(
            (_normalize_growth(yf_data.get('gross_margin')) if yf_data.get('gross_margin') else None), 1
        ))

        # Enhanced verdict with valuation
        if ps is not None and growth is not None:
            price_data_obj = PriceData(**{k: v for k, v in price_dict.items() if k in PriceData.__dataclass_fields__})
            val_signal = analyze_valuation(
                fundamental_verdict=verdict,
                ndr=ndr,
                revenue_growth=growth_raw,
                price_data=price_data_obj,
                category_stage=info.get('category_stage', 'unknown'),
            )
            enhanced = compute_enhanced_verdict(
                fundamental_verdict=verdict,
                confidence=confidence,
                valuation_signal=val_signal,
                ndr=ndr,
                revenue_growth=growth_raw,
            )

            st.markdown("---")
            st.subheader("Enhanced Verdict (with Valuation)")
            ev1, ev2, ev3, ev4 = st.columns(4)
            ev1.metric("Final Recommendation", enhanced.final_recommendation)
            ev2.metric("Opportunity Score", f"{val_signal.opportunity_score:.0f}/100")
            ev3.metric("Valuation Tier", val_signal.valuation_tier.replace('_', ' ').title())
            ev4.metric("Timing", val_signal.timing_signal.replace('_', ' ').title())
            st.caption(val_signal.valuation_rationale)
    else:
        st.info("Live market data unavailable. Showing database-only analysis.")

    st.markdown("---")

    # --- Staleness Warnings ---
    stale = vd.get('staleness_warning', True)
    stale_fields = vd.get('stale_fields', [])
    if stale and stale_fields:
        st.subheader("Data Staleness Warnings")
        for sf in stale_fields:
            st.warning(f"Stale: {sf}")

    # --- Research Recommendations ---
    recs = vd.get('research_recommendations', [])
    if recs:
        with st.expander("Research Recommendations", expanded=False):
            for i, rec in enumerate(recs, 1):
                st.markdown(f"{i}. {rec}")

    # --- Notes ---
    notes = info.get('notes', '')
    if notes:
        st.caption(f"Notes: {notes}")


# ============================================================
# VIEW 3: SCREENING
# ============================================================

def render_screening(df: pd.DataFrame):
    """Advanced filtering, sorting, and scatter plot view."""

    st.header("Screening & Comparison")

    # --- Sort Controls ---
    sort_col = st.selectbox(
        "Sort By",
        ['Verdict', 'Confidence Score', 'NDR', 'Growth (%)', 'Data Tier',
         'Entry Signals', 'Exit Signals', 'Ticker'],
        index=1,
    )
    sort_asc = st.radio("Order", ["Descending", "Ascending"], horizontal=True, index=0)

    ascending = sort_asc == "Ascending"

    # Sort — handle Verdict specially
    if sort_col == 'Verdict':
        verdict_sort = {v: i for i, v in enumerate(VERDICT_ORDER)}
        sorted_df = df.copy()
        sorted_df['_sort'] = sorted_df['Verdict'].map(verdict_sort).fillna(99)
        sorted_df = sorted_df.sort_values('_sort', ascending=ascending).drop(columns=['_sort'])
    else:
        sorted_df = df.sort_values(sort_col, ascending=ascending, na_position='last')

    # --- Extended Table ---
    ext_df = sorted_df[[
        'Ticker', 'Name', 'Verdict', 'Confidence', 'Confidence Score',
        'Data Tier', 'NDR', 'Growth (%)', 'ARR ($M)', 'Customers 100K+',
        'Gross Retention', 'DBNE', 'Category Stage', 'Big Tech Threat',
        'Switching Cost', 'Entry Signals', 'Exit Signals',
    ]].copy()

    ext_df['NDR'] = ext_df['NDR'].apply(lambda x: f"{x:.0f}%" if pd.notna(x) else "N/A")
    ext_df['Growth (%)'] = ext_df['Growth (%)'].apply(lambda x: f"{x:.0f}%" if pd.notna(x) else "N/A")
    ext_df['Confidence Score'] = ext_df['Confidence Score'].apply(lambda x: f"{x:.0%}")
    ext_df['Data Tier'] = ext_df['Data Tier'].apply(lambda x: f"T{x}")
    ext_df['ARR ($M)'] = ext_df['ARR ($M)'].apply(lambda x: f"${x:.0f}M" if pd.notna(x) else "N/A")
    ext_df['Gross Retention'] = ext_df['Gross Retention'].apply(lambda x: f"{x}%" if pd.notna(x) else "N/A")
    ext_df['DBNE'] = ext_df['DBNE'].apply(lambda x: f"{x}%" if pd.notna(x) else "N/A")
    ext_df['Customers 100K+'] = ext_df['Customers 100K+'].apply(lambda x: str(int(x)) if pd.notna(x) else "N/A")

    st.dataframe(ext_df, use_container_width=True, height=600, hide_index=True)

    st.markdown("---")

    # --- Scatter Plot ---
    st.subheader("Company Scatter Plot")

    scatter_left, scatter_right = st.columns(2)
    with scatter_left:
        x_axis = st.selectbox("X Axis", ['NDR', 'Growth (%)', 'Confidence Score', 'Entry Signals', 'Data Tier'])
    with scatter_right:
        y_axis = st.selectbox("Y Axis", ['Growth (%)', 'NDR', 'Confidence Score', 'Entry Signals', 'Data Tier'], index=0)

    # Use numeric df for scatter
    scatter_df = df[['Ticker', 'Name', 'Verdict', x_axis, y_axis, 'Data Tier']].dropna(subset=[x_axis, y_axis])

    if len(scatter_df) > 0:
        fig_scatter = px.scatter(
            scatter_df,
            x=x_axis,
            y=y_axis,
            color='Verdict',
            color_discrete_map=VERDICT_COLORS,
            hover_name='Ticker',
            hover_data=['Name', 'Data Tier'],
            title=f"{y_axis} vs {x_axis}",
        )
        fig_scatter.update_layout(margin=dict(t=40, b=0), height=500)
        fig_scatter.update_traces(marker=dict(size=12, line=dict(width=1, color='white')))
        st.plotly_chart(fig_scatter, use_container_width=True)
    else:
        st.warning("No data available for the selected axes. Try different columns.")


# ============================================================
# VIEW 4: DATA QUALITY
# ============================================================

def render_data_quality(db: dict, verdicts: dict):
    """Data completeness, staleness, and research recommendations."""

    st.header("Data Quality Dashboard")

    # --- Overall Completeness ---
    total_fields = 0
    present_fields = 0

    for ticker, info in db.items():
        for f in COMPLETENESS_FIELDS:
            total_fields += 1
            val = info.get(f)
            if f in ('big_tech_threat', 'category_stage', 'switching_cost'):
                if val is not None and val != 'unknown':
                    present_fields += 1
            else:
                if val is not None:
                    present_fields += 1

    completeness_pct = present_fields / total_fields if total_fields > 0 else 0

    m1, m2, m3 = st.columns(3)
    m1.metric("Overall Completeness", f"{completeness_pct:.0%}")
    m2.metric("Total Fields Tracked", total_fields)
    m3.metric("Fields Populated", present_fields)

    st.markdown("---")

    # --- Tier Distribution ---
    st.subheader("Data Tier Distribution")

    tier_groups = {1: [], 2: [], 3: [], 4: []}
    for ticker in db:
        v = verdicts.get(ticker, {})
        t = v.get('verdict', {}).get('data_tier', 4)
        tier_groups[t].append(ticker)

    t1, t2, t3, t4 = st.columns(4)
    t1.metric("Tier 1 (Direct NDR)", len(tier_groups[1]))
    t2.metric("Tier 2 (Variant)", len(tier_groups[2]))
    t3.metric("Tier 3 (Derived)", len(tier_groups[3]))
    t4.metric("Tier 4 (Insufficient)", len(tier_groups[4]))

    for tier_num, companies in tier_groups.items():
        with st.expander(f"Tier {tier_num} — {len(companies)} companies"):
            if companies:
                st.write(", ".join(sorted(companies)))
            else:
                st.write("None")

    st.markdown("---")

    # --- Completeness Heatmap ---
    st.subheader("Data Completeness Heatmap")

    tickers_sorted = sorted(db.keys())
    matrix_data = []

    for ticker in tickers_sorted:
        info = db[ticker]
        row = {}
        for f in COMPLETENESS_FIELDS:
            val = info.get(f)
            if f in ('big_tech_threat', 'category_stage', 'switching_cost'):
                row[f] = 1 if (val is not None and val != 'unknown') else 0
            else:
                row[f] = 1 if val is not None else 0
        matrix_data.append(row)

    heatmap_df = pd.DataFrame(matrix_data, index=tickers_sorted)

    # Clean column names for display
    col_labels = [c.replace('_', ' ').title() for c in heatmap_df.columns]

    fig_heatmap = go.Figure(data=go.Heatmap(
        z=heatmap_df.values,
        x=col_labels,
        y=heatmap_df.index,
        colorscale=[[0, '#EF5350'], [1, '#66BB6A']],
        showscale=False,
        hovertemplate='%{y} — %{x}: %{z}<extra></extra>',
    ))
    fig_heatmap.update_layout(
        height=max(25 * len(tickers_sorted), 400),
        margin=dict(t=20, b=0, l=0, r=0),
        xaxis=dict(side='top', tickangle=-45),
        yaxis=dict(autorange='reversed'),
    )
    st.plotly_chart(fig_heatmap, use_container_width=True)

    st.caption("Green = data present, Red = missing/unknown")

    st.markdown("---")

    # --- Staleness Dashboard ---
    st.subheader("Staleness Warnings")

    stale_companies = []
    for ticker in sorted(db.keys()):
        v = verdicts.get(ticker, {})
        vd = v.get('verdict', {})
        if vd.get('staleness_warning'):
            stale_fields = vd.get('stale_fields', [])
            stale_companies.append({
                'Ticker': ticker,
                'Name': db[ticker].get('name', ticker),
                'Stale Fields': '; '.join(stale_fields) if stale_fields else 'No date recorded',
            })

    if stale_companies:
        st.warning(f"{len(stale_companies)} of {len(db)} companies have staleness warnings.")
        st.dataframe(
            pd.DataFrame(stale_companies),
            use_container_width=True,
            hide_index=True,
            height=min(35 * len(stale_companies) + 38, 500),
        )
    else:
        st.success("All company data is fresh!")

    st.markdown("---")

    # --- Aggregated Research Recommendations ---
    st.subheader("Research Recommendations")

    ndr_recs = []
    competitive_recs = []
    other_recs = []

    for ticker in sorted(db.keys()):
        v = verdicts.get(ticker, {})
        vd = v.get('verdict', {})
        for rec in vd.get('research_recommendations', []):
            rec_with_ticker = f"**{ticker}**: {rec}"
            if 'NDR' in rec or 'NRR' in rec or 'DBNE' in rec or 'retention' in rec.lower():
                ndr_recs.append(rec_with_ticker)
            elif 'Big Tech' in rec or 'category' in rec.lower() or 'switching' in rec.lower():
                competitive_recs.append(rec_with_ticker)
            else:
                other_recs.append(rec_with_ticker)

    with st.expander(f"NDR / Retention Research ({len(ndr_recs)} items)", expanded=False):
        for rec in ndr_recs:
            st.markdown(f"- {rec}")
        if not ndr_recs:
            st.write("No NDR research needed.")

    with st.expander(f"Competitive Assessment ({len(competitive_recs)} items)", expanded=False):
        for rec in competitive_recs:
            st.markdown(f"- {rec}")
        if not competitive_recs:
            st.write("All competitive assessments complete.")

    with st.expander(f"Other Research ({len(other_recs)} items)", expanded=False):
        for rec in other_recs:
            st.markdown(f"- {rec}")
        if not other_recs:
            st.write("No additional research needed.")


# ============================================================
# MAIN
# ============================================================

def main():
    st.set_page_config(
        page_title="PLG Stock Analysis",
        page_icon=":chart_with_upwards_trend:",
        layout="wide",
        initial_sidebar_state="expanded",
    )

    # Load data
    db = load_database()
    verdicts = compute_all_verdicts(json.dumps(db, default=str))
    df = build_portfolio_dataframe(db, verdicts)

    # Sidebar
    nav, filters = render_sidebar(db, df)
    filtered_df = apply_filters(df, filters)

    # Empty state
    if len(filtered_df) == 0:
        st.warning("No companies match the current filters. Adjust filters in the sidebar.")
        return

    # Route to view
    if nav == "Portfolio Overview":
        render_portfolio_overview(filtered_df, verdicts)
    elif nav == "Company Deep Dive":
        render_company_deep_dive(db, verdicts, filters.get('selected_ticker'))
    elif nav == "Screening":
        render_screening(filtered_df)
    elif nav == "Data Quality":
        render_data_quality(db, verdicts)


if __name__ == "__main__":
    main()
