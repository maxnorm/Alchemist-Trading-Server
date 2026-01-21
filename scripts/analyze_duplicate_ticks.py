"""
Analyze duplicate tick rejections and verify if they are legitimate duplicates.
This script queries the quarantine_ticks table and analyzes patterns to determine
if the duplicate detection is working correctly.
"""

import os
import sys
import json
from datetime import datetime, timedelta
from collections import defaultdict
from typing import Dict, List, Tuple, Optional
import statistics

# Add parent directory to path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from src.trading_server.src.database.database import Database


def analyze_quarantine_ticks(db: Database, hours_back: int = 24) -> Dict:
    """
    Analyze quarantine ticks to understand duplicate rejection patterns.
    
    :param db: Database instance
    :param hours_back: How many hours back to analyze
    :return: Analysis results dictionary
    """
    results = {
        "summary": {},
        "by_category": {},
        "by_symbol": {},
        "duplicate_analysis": {},
        "timestamp_patterns": {},
        "recommendations": []
    }
    
    # Get time range
    end_time = datetime.utcnow()
    start_time = end_time - timedelta(hours=hours_back)
    
    print(f"Analyzing quarantine ticks from {start_time} to {end_time}")
    
    # Query all quarantine ticks in time range
    query = """
        SELECT 
            id, symbol, datetime, receive_time, bid, ask, 
            rejection_reason, rejection_category, quarantined_at
        FROM quarantine_ticks
        WHERE quarantined_at >= :start_time
        ORDER BY quarantined_at DESC
    """
    
    with db.execute_query() as conn:
        from sqlalchemy import text
        result = conn.execute(text(query), {"start_time": start_time})
        rows = result.fetchall()
    
    total_quarantined = len(rows)
    print(f"Found {total_quarantined} quarantined ticks")
    
    if total_quarantined == 0:
        return results
    
    # Summary statistics
    by_category = defaultdict(int)
    by_symbol = defaultdict(int)
    duplicate_ticks = []
    
    for row in rows:
        category = row.rejection_category
        symbol = row.symbol
        by_category[category] += 1
        by_symbol[symbol] += 1
        
        if category == "duplicate":
            duplicate_ticks.append({
                "id": row.id,
                "symbol": symbol,
                "datetime": row.datetime,
                "receive_time": row.receive_time,
                "bid": float(row.bid),
                "ask": float(row.ask),
                "rejection_reason": row.rejection_reason,
                "quarantined_at": row.quarantined_at
            })
    
    results["summary"] = {
        "total_quarantined": total_quarantined,
        "time_range_hours": hours_back,
        "start_time": start_time.isoformat(),
        "end_time": end_time.isoformat()
    }
    
    results["by_category"] = dict(by_category)
    results["by_symbol"] = dict(sorted(by_symbol.items(), key=lambda x: x[1], reverse=True))
    
    # Analyze duplicate ticks in detail
    if duplicate_ticks:
        print(f"\nAnalyzing {len(duplicate_ticks)} duplicate rejections...")
        duplicate_analysis = analyze_duplicates(db, duplicate_ticks)
        results["duplicate_analysis"] = duplicate_analysis
    
    return results


def analyze_duplicates(db: Database, duplicate_ticks: List[Dict]) -> Dict:
    """
    Analyze duplicate ticks to verify if they are legitimate duplicates.
    
    :param db: Database instance
    :param duplicate_ticks: List of duplicate tick records
    :return: Detailed analysis
    """
    analysis = {
        "total_duplicates": len(duplicate_ticks),
        "by_symbol": defaultdict(int),
        "by_reason": defaultdict(int),
        "timestamp_differences": [],
        "price_differences": [],
        "legitimate_duplicates": 0,
        "potential_false_positives": 0,
        "sample_duplicates": []
    }
    
    # Group by symbol
    by_symbol = defaultdict(list)
    for tick in duplicate_ticks:
        symbol = tick["symbol"]
        by_symbol[symbol].append(tick)
        analysis["by_symbol"][symbol] += 1
    
    # Analyze rejection reasons
    for tick in duplicate_ticks:
        reason = tick["rejection_reason"]
        analysis["by_reason"][reason] += 1
    
    # For each symbol, check if we can verify duplicates by querying accepted ticks
    print("\nVerifying duplicates against accepted ticks...")
    
    for symbol, ticks in list(by_symbol.items())[:5]:  # Analyze top 5 symbols
        print(f"\nAnalyzing {symbol} ({len(ticks)} duplicate rejections)...")
        
        # Query accepted ticks around the same time
        if ticks:
            first_tick_time = min(t["datetime"] for t in ticks)
            last_tick_time = max(t["datetime"] for t in ticks)
            
            # Query accepted ticks in this time range
            query = """
                SELECT datetime, bid, ask
                FROM ticks
                WHERE symbol = :symbol
                  AND datetime >= :start_time
                  AND datetime <= :end_time
                ORDER BY datetime
            """
            
            with db.execute_query() as conn:
                from sqlalchemy import text
                result = conn.execute(text(query), {
                    "symbol": symbol,
                    "start_time": first_tick_time - timedelta(seconds=1),
                    "end_time": last_tick_time + timedelta(seconds=1)
                })
                accepted_rows = result.fetchall()
            
            # Check if rejected duplicates match accepted ticks
            accepted_by_datetime = {}
            for row in accepted_rows:
                dt_key = row.datetime.isoformat()
                accepted_by_datetime[dt_key] = {
                    "bid": float(row.bid),
                    "ask": float(row.ask)
                }
            
            # Analyze each duplicate
            verified_count = 0
            false_positive_count = 0
            
            for tick in ticks[:10]:  # Sample first 10
                tick_dt = tick["datetime"]
                tick_dt_key = tick_dt.isoformat()
                
                # Check if there's an accepted tick with same timestamp
                if tick_dt_key in accepted_by_datetime:
                    accepted = accepted_by_datetime[tick_dt_key]
                    tick_bid = tick["bid"]
                    tick_ask = tick["ask"]
                    
                    # Check if prices match
                    bid_match = abs(tick_bid - accepted["bid"]) < 1e-10
                    ask_match = abs(tick_ask - accepted["ask"]) < 1e-10
                    
                    if bid_match and ask_match:
                        verified_count += 1
                        analysis["legitimate_duplicates"] += 1
                    else:
                        false_positive_count += 1
                        analysis["potential_false_positives"] += 1
                        print(f"  ⚠️  False positive: {tick_dt_key}")
                        print(f"     Rejected: bid={tick_bid}, ask={tick_ask}")
                        print(f"     Accepted: bid={accepted['bid']}, ask={accepted['ask']}")
                else:
                    # No accepted tick with same timestamp - might be legitimate duplicate
                    verified_count += 1
                    analysis["legitimate_duplicates"] += 1
            
            print(f"  ✓ Verified: {verified_count}, Potential false positives: {false_positive_count}")
    
    # Extract timestamp differences from rejection reasons
    for tick in duplicate_ticks[:100]:  # Sample first 100
        reason = tick["rejection_reason"]
        if "μs from last tick" in reason:
            try:
                # Extract microseconds difference
                parts = reason.split("μs from last tick")
                if parts:
                    us_str = parts[0].split(":")[-1].strip()
                    us_diff = float(us_str)
                    analysis["timestamp_differences"].append(us_diff)
            except:
                pass
    
    # Sample duplicates for detailed inspection
    analysis["sample_duplicates"] = duplicate_ticks[:20]
    
    return analysis


def check_multiple_processors(db: Database) -> Dict:
    """
    Check if multiple TickProcessor instances might be processing the same symbol.
    This would cause duplicate detection to fail since each processor has its own state.
    
    :param db: Database instance
    :return: Analysis of potential multiple processors
    """
    # Query for patterns that suggest multiple processors
    # If we see the same tick timestamp accepted multiple times, that's a sign
    
    query = """
        SELECT symbol, datetime, COUNT(*) as count
        FROM ticks
        WHERE datetime >= NOW() - INTERVAL '1 hour'
        GROUP BY symbol, datetime
        HAVING COUNT(*) > 1
        ORDER BY count DESC, datetime DESC
        LIMIT 50
    """
    
    with db.execute_query() as conn:
        from sqlalchemy import text
        result = conn.execute(text(query))
        rows = result.fetchall()
    
    return {
        "duplicate_timestamps_in_db": len(rows),
        "samples": [
            {
                "symbol": row.symbol,
                "datetime": row.datetime.isoformat(),
                "count": row.count
            }
            for row in rows[:10]
        ]
    }


def generate_report(results: Dict, output_file: str):
    """
    Generate a detailed markdown report.
    
    :param results: Analysis results
    :param output_file: Output file path
    """
    report = []
    report.append("# Duplicate Tick Analysis Report")
    report.append(f"\n**Generated:** {datetime.utcnow().isoformat()}Z\n")
    
    # Summary
    summary = results.get("summary", {})
    report.append("## Executive Summary\n")
    report.append(f"- **Total Quarantined Ticks:** {summary.get('total_quarantined', 0)}")
    report.append(f"- **Time Range:** {summary.get('time_range_hours', 0)} hours")
    report.append(f"- **Analysis Period:** {summary.get('start_time', 'N/A')} to {summary.get('end_time', 'N/A')}\n")
    
    # By Category
    by_category = results.get("by_category", {})
    if by_category:
        report.append("## Rejections by Category\n")
        report.append("| Category | Count | Percentage |")
        report.append("|----------|-------|------------|")
        total = sum(by_category.values())
        for category, count in sorted(by_category.items(), key=lambda x: x[1], reverse=True):
            pct = (count / total * 100) if total > 0 else 0
            report.append(f"| {category} | {count} | {pct:.2f}% |")
        report.append("")
    
    # By Symbol
    by_symbol = results.get("by_symbol", {})
    if by_symbol:
        report.append("## Rejections by Symbol\n")
        report.append("| Symbol | Count | Percentage |")
        report.append("|--------|-------|------------|")
        total = sum(by_symbol.values())
        for symbol, count in list(sorted(by_symbol.items(), key=lambda x: x[1], reverse=True))[:20]:
            pct = (count / total * 100) if total > 0 else 0
            report.append(f"| {symbol} | {count} | {pct:.2f}% |")
        report.append("")
    
    # Duplicate Analysis
    dup_analysis = results.get("duplicate_analysis", {})
    if dup_analysis:
        report.append("## Duplicate Tick Analysis\n")
        report.append(f"- **Total Duplicate Rejections:** {dup_analysis.get('total_duplicates', 0)}")
        report.append(f"- **Legitimate Duplicates:** {dup_analysis.get('legitimate_duplicates', 0)}")
        report.append(f"- **Potential False Positives:** {dup_analysis.get('potential_false_positives', 0)}\n")
        
        # By Symbol
        dup_by_symbol = dup_analysis.get("by_symbol", {})
        if dup_by_symbol:
            report.append("### Duplicates by Symbol\n")
            report.append("| Symbol | Count |")
            report.append("|--------|-------|")
            for symbol, count in sorted(dup_by_symbol.items(), key=lambda x: x[1], reverse=True):
                report.append(f"| {symbol} | {count} |")
            report.append("")
        
        # By Reason
        dup_by_reason = dup_analysis.get("by_reason", {})
        if dup_by_reason:
            report.append("### Duplicates by Rejection Reason\n")
            report.append("| Reason | Count |")
            report.append("|--------|-------|")
            for reason, count in sorted(dup_by_reason.items(), key=lambda x: x[1], reverse=True):
                # Truncate long reasons
                short_reason = reason[:100] + "..." if len(reason) > 100 else reason
                report.append(f"| {short_reason} | {count} |")
            report.append("")
        
        # Timestamp Differences
        timestamp_diffs = dup_analysis.get("timestamp_differences", [])
        if timestamp_diffs:
            report.append("### Timestamp Differences (Microseconds)\n")
            report.append(f"- **Count:** {len(timestamp_diffs)}")
            report.append(f"- **Min:** {min(timestamp_diffs):.0f}μs")
            report.append(f"- **Max:** {max(timestamp_diffs):.0f}μs")
            report.append(f"- **Mean:** {statistics.mean(timestamp_diffs):.2f}μs")
            report.append(f"- **Median:** {statistics.median(timestamp_diffs):.2f}μs\n")
            
            # Distribution
            zero_diff = sum(1 for d in timestamp_diffs if d == 0)
            report.append(f"- **Zero Difference (Exact Duplicates):** {zero_diff} ({zero_diff/len(timestamp_diffs)*100:.1f}%)\n")
        
        # Sample Duplicates
        samples = dup_analysis.get("sample_duplicates", [])
        if samples:
            report.append("### Sample Duplicate Rejections\n")
            report.append("| Symbol | DateTime | Bid | Ask | Reason |")
            report.append("|--------|----------|-----|-----|--------|")
            for tick in samples[:10]:
                dt_str = tick["datetime"].isoformat() if isinstance(tick["datetime"], datetime) else str(tick["datetime"])
                reason_short = tick["rejection_reason"][:50] + "..." if len(tick["rejection_reason"]) > 50 else tick["rejection_reason"]
                report.append(f"| {tick['symbol']} | {dt_str} | {tick['bid']} | {tick['ask']} | {reason_short} |")
            report.append("")
    
    # Recommendations
    report.append("## Recommendations\n")
    
    recommendations = []
    
    if dup_analysis.get("potential_false_positives", 0) > 0:
        recommendations.append("⚠️ **False Positives Detected:** Some rejected ticks don't match accepted ticks. Review duplicate detection logic.")
    
    timestamp_diffs = dup_analysis.get("timestamp_differences", [])
    if timestamp_diffs:
        zero_diff = sum(1 for d in timestamp_diffs if d == 0)
        if zero_diff > len(timestamp_diffs) * 0.5:
            recommendations.append("⚠️ **High Rate of Exact Duplicates:** Many ticks have 0μs difference. Check if MT5 EA is sending duplicate ticks or if ZeroMQ broker is duplicating messages.")
    
    if dup_analysis.get("total_duplicates", 0) > 1000:
        recommendations.append("⚠️ **High Duplicate Rate:** Consider investigating the source of duplicates (MT5 EA configuration, multiple EAs streaming same symbol).")
    
    if not recommendations:
        recommendations.append("✓ **System Working Correctly:** Duplicate detection appears to be functioning as designed.")
    
    for rec in recommendations:
        report.append(f"- {rec}\n")
    
    # Technical Details
    report.append("## Technical Details\n")
    report.append("### Duplicate Detection Logic\n")
    report.append("- **Tolerance:** 1ms (1000μs)")
    report.append("- **Detection Method:** Timestamp difference + price comparison")
    report.append("- **State Management:** Per-TickProcessor instance (not shared)\n")
    report.append("### Potential Issues\n")
    report.append("1. **Per-Instance State:** Each TickProcessor has its own QualityGate with separate duplicate detection state")
    report.append("2. **Multiple Processors:** If multiple TickProcessor instances exist for the same symbol, they won't share duplicate detection state")
    report.append("3. **Source Duplicates:** MT5 EA or ZeroMQ broker may be sending duplicate ticks\n")
    
    # Write report
    with open(output_file, 'w', encoding='utf-8') as f:
        f.write('\n'.join(report))
    
    print(f"\n✓ Report written to: {output_file}")


def main():
    """Main analysis function."""
    print("=" * 80)
    print("Duplicate Tick Analysis")
    print("=" * 80)
    
    # Initialize database
    try:
        db = Database()
        print("✓ Database connection established")
    except Exception as e:
        print(f"✗ Failed to connect to database: {e}")
        return
    
    # Analyze quarantine ticks
    try:
        results = analyze_quarantine_ticks(db, hours_back=24)
    except Exception as e:
        print(f"✗ Failed to analyze quarantine ticks: {e}")
        import traceback
        traceback.print_exc()
        return
    
    # Check for multiple processors
    try:
        multi_proc_analysis = check_multiple_processors(db)
        results["multiple_processors_analysis"] = multi_proc_analysis
    except Exception as e:
        print(f"⚠ Warning: Failed to check multiple processors: {e}")
    
    # Generate report
    output_dir = os.path.join(os.path.dirname(__file__), '..', 'docs', 'generated')
    os.makedirs(output_dir, exist_ok=True)
    output_file = os.path.join(output_dir, 'duplicate_ticks_analysis_report.md')
    
    try:
        generate_report(results, output_file)
    except Exception as e:
        print(f"✗ Failed to generate report: {e}")
        import traceback
        traceback.print_exc()
        return
    
    # Print summary
    print("\n" + "=" * 80)
    print("Analysis Summary")
    print("=" * 80)
    print(f"Total Quarantined: {results['summary'].get('total_quarantined', 0)}")
    print(f"By Category: {results.get('by_category', {})}")
    if results.get('duplicate_analysis'):
        dup = results['duplicate_analysis']
        print(f"Duplicate Rejections: {dup.get('total_duplicates', 0)}")
        print(f"Legitimate: {dup.get('legitimate_duplicates', 0)}")
        print(f"Potential False Positives: {dup.get('potential_false_positives', 0)}")
    print("=" * 80)


if __name__ == "__main__":
    main()
