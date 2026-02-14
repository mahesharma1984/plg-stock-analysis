#!/usr/bin/env python3
"""
PLG Analysis - Batch Analyzer

Analyzes companies from the PLG investment thesis using shared
logic in plg_core.py and company data from company_database.json.

Usage:
    python plg_batch_analyzer.py              # Analyze all companies
    python plg_batch_analyzer.py MDB SNOW     # Analyze specific tickers
"""

import argparse
import json
import csv
from datetime import datetime
from typing import List, Dict, Optional
import sys

from plg_core import (
    CompanyData,
    VerdictResult,
    load_company_database,
    build_company_data,
    fetch_yfinance_data,
    fetch_sec_edgar_data,
    compute_verdict,
    check_staleness,
    format_verdict,
    format_growth,
    format_currency,
    format_confidence,
    _normalize_growth,
)


# ============================================================
# ANALYSIS FUNCTIONS
# ============================================================

def analyze_company(ticker: str, company_info: dict) -> tuple:
    """Analyze a single company.

    Fetches live data from yfinance, builds CompanyData,
    and computes verdict using plg_core.
    """
    print(f"  {ticker}...", end='', flush=True)

    # Fetch live data
    yf_data = fetch_yfinance_data(ticker)
    sec_data = fetch_sec_edgar_data(ticker, company_info.get('cik', ''))

    # Build CompanyData from database + live data
    company = build_company_data(ticker, company_info, yf_data, sec_data)

    # Compute verdict
    verdict = compute_verdict(company)

    print(f" {verdict.verdict}", flush=True)

    return company, verdict


def batch_analyze(
    database: Dict[str, dict],
    tickers: Optional[List[str]] = None,
) -> List[Dict]:
    """Analyze multiple companies.

    Args:
        database: Company database dict (ticker -> info).
        tickers: Optional list of specific tickers. None = all.

    Returns:
        List of dicts with 'company' and 'verdict' keys.
    """
    if tickers is None:
        tickers = list(database.keys())

    print(f"\n{'='*60}")
    print(f"PLG BATCH ANALYSIS - {len(tickers)} Companies")
    print(f"{'='*60}\n")

    print("Analyzing companies:")

    results = []

    for ticker in tickers:
        if ticker not in database:
            print(f"  {ticker}... SKIPPED (not in database)")
            continue

        try:
            company, verdict = analyze_company(ticker, database[ticker])

            results.append({
                'company': company,
                'verdict': verdict,
            })
        except Exception as e:
            print(f" ERROR: {e}")
            continue

    return results


# ============================================================
# SUMMARY & OUTPUT
# ============================================================

def generate_summary(results: List[Dict]) -> Dict:
    """Generate summary statistics."""

    verdict_counts = {}
    by_verdict = {
        'STRONG_BUY': [],
        'BUY': [],
        'WATCH': [],
        'SELL': [],
        'AVOID': [],
    }

    for r in results:
        verdict = r['verdict'].verdict
        ticker = r['company'].ticker
        ndr = r['company'].ndr
        growth = r['company'].revenue_growth_yoy

        verdict_counts[verdict] = verdict_counts.get(verdict, 0) + 1

        growth_pct = _normalize_growth(growth)
        by_verdict.setdefault(verdict, []).append({
            'ticker': ticker,
            'name': r['company'].name,
            'ndr': ndr,
            'growth_pct': growth_pct,
            'confidence': r['verdict'].confidence,
            'data_tier': r['verdict'].data_tier,
        })

    return {
        'total_analyzed': len(results),
        'verdict_counts': verdict_counts,
        'by_verdict': by_verdict,
    }


def print_summary(summary: Dict, results: List[Dict]):
    """Print formatted summary to console."""

    print(f"\n{'='*60}")
    print(f"SUMMARY: {summary['total_analyzed']} Companies Analyzed")
    print(f"{'='*60}\n")

    # Verdict breakdown
    print("VERDICT BREAKDOWN:")
    for verdict in ['STRONG_BUY', 'BUY', 'WATCH', 'SELL', 'AVOID']:
        count = summary['verdict_counts'].get(verdict, 0)
        if count > 0:
            print(f"  {format_verdict(verdict)}: {count}")

    # Top picks
    print(f"\nSTRONG BUY ({len(summary['by_verdict']['STRONG_BUY'])}):")
    for co in summary['by_verdict']['STRONG_BUY']:
        ndr_str = f"NDR {co['ndr']}%" if co['ndr'] else "NDR N/A"
        growth_str = f"{co['growth_pct']:.0f}% growth" if co['growth_pct'] else "N/A"
        print(f"  {co['ticker']:6s} ({co['name'][:20]:20s}) - {ndr_str}, {growth_str} [Tier {co['data_tier']}]")

    print(f"\nBUY ({len(summary['by_verdict']['BUY'])}):")
    for co in summary['by_verdict']['BUY'][:10]:
        ndr_str = f"NDR {co['ndr']}%" if co['ndr'] else "NDR N/A"
        growth_str = f"{co['growth_pct']:.0f}% growth" if co['growth_pct'] else "N/A"
        print(f"  {co['ticker']:6s} ({co['name'][:20]:20s}) - {ndr_str}, {growth_str} [Tier {co['data_tier']}]")

    print(f"\nWATCH ({len(summary['by_verdict']['WATCH'])}):")
    for co in summary['by_verdict']['WATCH'][:8]:
        ndr_str = f"NDR {co['ndr']}%" if co['ndr'] else "NDR N/A"
        print(f"  {co['ticker']:6s} ({co['name'][:20]:20s}) - {ndr_str} [Tier {co['data_tier']}]")
    remaining = len(summary['by_verdict']['WATCH']) - 8
    if remaining > 0:
        print(f"  ... and {remaining} more")

    sell_avoid = summary['by_verdict']['SELL'] + summary['by_verdict']['AVOID']
    print(f"\nSELL/AVOID ({len(sell_avoid)}):")
    for co in sell_avoid:
        ndr_str = f"NDR {co['ndr']}%" if co['ndr'] else "NDR N/A"
        print(f"  {co['ticker']:6s} ({co['name'][:20]:20s}) - {ndr_str} [Tier {co['data_tier']}]")

    # Staleness warnings
    stale_companies = [
        r for r in results if r['verdict'].staleness_warning
    ]
    if stale_companies:
        print(f"\nSTALENESS WARNINGS ({len(stale_companies)}):")
        for r in stale_companies[:5]:
            ticker = r['company'].ticker
            fields = ', '.join(r['verdict'].stale_fields[:2])
            print(f"  {ticker}: {fields}")
        if len(stale_companies) > 5:
            print(f"  ... and {len(stale_companies) - 5} more")

    # Research recommendations (top 3)
    recs = [
        (r['company'].ticker, r['verdict'].research_recommendations)
        for r in results
        if r['verdict'].research_recommendations
    ]
    if recs:
        print(f"\nTOP RESEARCH RECOMMENDATIONS:")
        shown = 0
        for ticker, rec_list in recs:
            if shown >= 3:
                break
            print(f"  {ticker}: {rec_list[0][:80]}...")
            shown += 1


def save_results(results: List[Dict], summary: Dict):
    """Save results to JSON and CSV."""

    # JSON - Full data
    output_data = []
    for r in results:
        output_data.append({
            'ticker': r['company'].ticker,
            'name': r['company'].name,
            'verdict': r['verdict'].verdict,
            'confidence': r['verdict'].confidence,
            'confidence_score': r['verdict'].confidence_score,
            'data_tier': r['verdict'].data_tier,
            'ndr': r['company'].ndr,
            'revenue_growth_yoy': r['company'].revenue_growth_yoy,
            'market_cap': r['company'].market_cap,
            'big_tech_threat': r['company'].big_tech_threat,
            'category_stage': r['company'].category_stage,
            'entry_signals': r['verdict'].entry_signals_met,
            'exit_signals': r['verdict'].exit_signals_triggered,
            'rationale': r['verdict'].rationale,
            'staleness_warning': r['verdict'].staleness_warning,
            'research_recommendations': r['verdict'].research_recommendations[:2],
        })

    with open('plg_batch_results.json', 'w') as f:
        json.dump({
            'analyzed_at': datetime.now().isoformat(),
            'summary': {
                'total_analyzed': summary['total_analyzed'],
                'verdict_counts': summary['verdict_counts'],
            },
            'results': output_data,
        }, f, indent=2)

    # CSV - Summary view
    with open('plg_batch_summary.csv', 'w', newline='') as f:
        writer = csv.DictWriter(f, fieldnames=[
            'ticker', 'name', 'verdict', 'confidence', 'data_tier',
            'ndr', 'growth_pct', 'market_cap', 'big_tech_threat', 'category_stage'
        ])
        writer.writeheader()

        for r in results:
            growth_pct = _normalize_growth(r['company'].revenue_growth_yoy)

            writer.writerow({
                'ticker': r['company'].ticker,
                'name': r['company'].name,
                'verdict': r['verdict'].verdict,
                'confidence': r['verdict'].confidence,
                'data_tier': r['verdict'].data_tier,
                'ndr': r['company'].ndr,
                'growth_pct': f"{growth_pct:.1f}" if growth_pct else "",
                'market_cap': r['company'].market_cap,
                'big_tech_threat': r['company'].big_tech_threat,
                'category_stage': r['company'].category_stage,
            })

    print(f"\nResults saved:")
    print(f"   plg_batch_results.json (full data)")
    print(f"   plg_batch_summary.csv (spreadsheet view)")


# ============================================================
# FRESHNESS CHECK
# ============================================================

def print_freshness_report(database: dict):
    """Check data freshness for all companies without running full analysis."""
    print(f"\n{'='*60}")
    print(f"DATA FRESHNESS REPORT - {len(database)} Companies")
    print(f"{'='*60}\n")

    missing_date = []
    stale = []
    fresh = []

    for ticker, info in sorted(database.items()):
        # Build minimal CompanyData (no API calls)
        company = build_company_data(ticker, info)
        is_stale, fields = check_staleness(company)

        if not company.data_updated:
            missing_date.append(ticker)
        elif is_stale:
            # Parse days old for display
            updated = datetime.strptime(company.data_updated, '%Y-%m-%d')
            days_old = (datetime.now() - updated).days
            stale.append((ticker, days_old, fields))
        else:
            updated = datetime.strptime(company.data_updated, '%Y-%m-%d')
            days_old = (datetime.now() - updated).days
            fresh.append((ticker, days_old))

    if missing_date:
        print(f"MISSING DATES (no data_updated):")
        print(f"  {', '.join(missing_date)}")
        print()

    if stale:
        print(f"STALE DATA:")
        for ticker, days, fields in stale:
            print(f"  {ticker}: {days} days old — {', '.join(fields)}")
        print()

    if fresh:
        print(f"FRESH (within thresholds):")
        for ticker, days in fresh:
            print(f"  {ticker}: {days} days old")
        print()

    print(f"{'='*60}")
    print(f"SUMMARY:")
    print(f"  Fresh:        {len(fresh)} / {len(database)}")
    print(f"  Stale:        {len(stale)} / {len(database)}")
    print(f"  Missing date: {len(missing_date)} / {len(database)}")
    print(f"{'='*60}\n")


# ============================================================
# MAIN
# ============================================================

if __name__ == "__main__":

    parser = argparse.ArgumentParser(
        description='PLG Batch Analyzer - Thesis-based investment analysis',
        usage='%(prog)s [tickers ...] [--check-freshness]',
    )
    parser.add_argument('tickers', nargs='*', help='Specific tickers to analyze (default: all)')
    parser.add_argument('--check-freshness', action='store_true',
                        help='Check data freshness without running full analysis')
    args = parser.parse_args()

    # Load company database from JSON
    database = load_company_database()

    if args.check_freshness:
        print_freshness_report(database)
    else:
        tickers = [t.upper() for t in args.tickers] if args.tickers else None
        if tickers:
            print(f"Analyzing specific tickers: {', '.join(tickers)}")

        # Run batch analysis
        results = batch_analyze(database, tickers)

        # Generate summary
        summary = generate_summary(results)

        # Print results
        print_summary(summary, results)

        # Save to files
        save_results(results, summary)

        print(f"\n{'='*60}\n")
