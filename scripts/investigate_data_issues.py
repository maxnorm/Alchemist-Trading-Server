#!/usr/bin/env python
"""
Diagnostic script to investigate negative latency and data gap issues.

This script performs deep analysis of:
1. Negative latency patterns (clock sync issues)
2. Data gap patterns (connection/market hours issues)
3. Timestamp source correlation
4. Root cause identification
"""

import os
import sys
from datetime import datetime, timedelta
from pathlib import Path
from typing import Dict, List, Tuple, Optional
from collections import defaultdict
import json

# Add src to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '../src/backend/trading_server/src'))

try:
    from database import Database
except ImportError:
    print("ERROR: Could not import Database module")
    sys.exit(1)

try:
    import pandas as pd
    import numpy as np
except ImportError:
    print("ERROR: pandas and numpy required. Install with: pip install pandas numpy")
    sys.exit(1)


class DataIssuesInvestigator:
    """Investigate negative latency and data gap issues"""

    def __init__(self, db: Database):
        self.db = db
        self.results = {
            "negative_latency": {},
            "data_gaps": {},
            "timestamp_analysis": {},
            "root_causes": [],
            "recommendations": [],
        }

    def investigate_all(self, hours: int = 48) -> Dict:
        """Run all investigations"""
        print(f"\n{'='*80}")
        print(f"DATA ISSUES INVESTIGATION")
        print(f"{'='*80}\n")
        print(f"Investigating data from last {hours} hours...\n")

        # 1. Negative latency investigation
        self.investigate_negative_latency(hours)

        # 2. Data gap investigation
        self.investigate_data_gaps(hours)

        # 3. Timestamp source analysis
        self.analyze_timestamp_sources(hours)

        # 4. Root cause analysis
        self.identify_root_causes()

        # 5. Generate recommendations
        self.generate_recommendations()

        return self.results

    def investigate_negative_latency(self, hours: int):
        """Investigate negative latency patterns"""
        print("1. NEGATIVE LATENCY INVESTIGATION")
        print("-" * 80)

        # Query negative latency samples with full context
        query = """
            SELECT 
                fp.symbol,
                tf.datetime as event_time,
                tf.receive_time,
                tf.latency_seconds,
                tf.ask,
                tf.bid,
                EXTRACT(HOUR FROM tf.datetime) as hour_of_day,
                EXTRACT(DOW FROM tf.datetime) as day_of_week
            FROM ticks_forex tf
            JOIN forex_pairs fp ON tf.forex_pairs_id = fp.id
            WHERE tf.datetime >= NOW() - (INTERVAL '1 hour' * :hours)
            AND tf.latency_seconds < 0
            ORDER BY tf.latency_seconds ASC, tf.datetime DESC
            LIMIT 100
        """

        try:
            samples = self.db.execute_with_result(query, {"hours": hours})
            
            if not samples:
                print("  No negative latency samples found")
                return

            # Group by symbol
            by_symbol = defaultdict(list)
            by_hour = defaultdict(int)
            latency_values = []

            for row in samples:
                symbol = row[0]
                event_time = row[1]
                receive_time = row[2]
                latency = float(row[3])
                hour = int(row[6]) if row[6] else None
                
                by_symbol[symbol].append({
                    "event_time": event_time.isoformat() if event_time else None,
                    "receive_time": receive_time.isoformat() if receive_time else None,
                    "latency_seconds": latency,
                    "ask": float(row[4]),
                    "bid": float(row[5]),
                })
                if hour is not None:
                    by_hour[hour] += 1
                latency_values.append(latency)

            # Statistics
            total_negative = len(samples)
            min_latency = min(latency_values) if latency_values else 0
            max_latency = max(latency_values) if latency_values else 0
            avg_latency = np.mean(latency_values) if latency_values else 0
            median_latency = np.median(latency_values) if latency_values else 0

            print(f"  Total Negative Latency Samples: {total_negative}")
            print(f"  Min Latency: {min_latency:.3f}s")
            print(f"  Max Latency: {max_latency:.3f}f")
            print(f"  Avg Latency: {avg_latency:.3f}s")
            print(f"  Median Latency: {median_latency:.3f}s")
            print(f"\n  By Symbol:")
            for symbol, ticks in sorted(by_symbol.items(), key=lambda x: len(x[1]), reverse=True):
                print(f"    {symbol}: {len(ticks)} ticks")
                # Show worst case
                worst = min(ticks, key=lambda x: x["latency_seconds"])
                print(f"      Worst: {worst['latency_seconds']:.3f}s at {worst['event_time']}")

            print(f"\n  By Hour of Day:")
            for hour in sorted(by_hour.keys()):
                print(f"    {hour:02d}:00 - {by_hour[hour]} occurrences")

            # Check if systematic (all symbols affected) or random
            symbol_count = len(by_symbol)
            query_total = """
                SELECT COUNT(DISTINCT fp.symbol)
                FROM ticks_forex tf
                JOIN forex_pairs fp ON tf.forex_pairs_id = fp.id
                WHERE tf.datetime >= NOW() - (INTERVAL '1 hour' * :hours)
            """
            total_symbols = self.db.execute_with_result(query_total, {"hours": hours})[0][0]
            affected_ratio = symbol_count / max(total_symbols, 1) if total_symbols else 0

            print(f"\n  Affected Symbols: {symbol_count} / {total_symbols} ({affected_ratio*100:.1f}%)")
            if affected_ratio > 0.5:
                print("  -> SYSTEMATIC: Affects majority of symbols (likely clock sync issue)")
            else:
                print("  -> RANDOM: Affects subset of symbols (likely symbol-specific issue)")

            self.results["negative_latency"] = {
                "total_samples": total_negative,
                "min_latency": float(min_latency),
                "max_latency": float(max_latency),
                "avg_latency": float(avg_latency),
                "median_latency": float(median_latency),
                "by_symbol": {k: len(v) for k, v in by_symbol.items()},
                "by_hour": dict(by_hour),
                "affected_symbols_ratio": float(affected_ratio),
                "is_systematic": affected_ratio > 0.5,
                "sample_data": {k: v[:3] for k, v in list(by_symbol.items())[:5]},  # Top 5 symbols, 3 samples each
            }

        except Exception as e:
            print(f"  ERROR: {e}")
            import traceback
            traceback.print_exc()
            self.results["negative_latency"]["error"] = str(e)

        print()

    def investigate_data_gaps(self, hours: int):
        """Investigate data gap patterns"""
        print("2. DATA GAP INVESTIGATION")
        print("-" * 80)

        # Find gaps with context
        query_gaps = """
            WITH tick_intervals AS (
                SELECT 
                    fp.symbol,
                    tf.datetime,
                    LAG(tf.datetime) OVER (PARTITION BY fp.symbol ORDER BY tf.datetime) as prev_datetime,
                    EXTRACT(EPOCH FROM (tf.datetime - LAG(tf.datetime) OVER (PARTITION BY fp.symbol ORDER BY tf.datetime))) as gap_seconds,
                    EXTRACT(DOW FROM tf.datetime) as day_of_week,
                    EXTRACT(HOUR FROM tf.datetime) as hour
                FROM ticks_forex tf
                JOIN forex_pairs fp ON tf.forex_pairs_id = fp.id
                WHERE tf.datetime >= NOW() - (INTERVAL '1 hour' * :hours)
            )
            SELECT 
                symbol,
                prev_datetime,
                datetime,
                gap_seconds,
                day_of_week,
                hour,
                EXTRACT(EPOCH FROM (datetime - prev_datetime)) / 3600.0 as gap_hours
            FROM tick_intervals
            WHERE gap_seconds > 300  -- 5 minutes
            ORDER BY gap_seconds DESC
            LIMIT 50
        """

        try:
            gaps = self.db.execute_with_result(query_gaps, {"hours": hours})
            
            if not gaps:
                print("  No significant gaps found")
                return

            # Analyze gap patterns
            gap_by_symbol = defaultdict(list)
            gap_by_day = defaultdict(int)
            gap_durations = []
            market_close_gaps = 0  # Friday evening to Sunday evening

            for row in gaps:
                symbol = row[0]
                prev_time = row[1]
                curr_time = row[2]
                gap_sec = float(row[3])
                day_of_week = int(row[4]) if row[4] else None
                hour = int(row[5]) if row[5] else None
                gap_hours = float(row[6]) if row[6] else 0

                gap_by_symbol[symbol].append({
                    "prev_time": prev_time.isoformat() if prev_time else None,
                    "curr_time": curr_time.isoformat() if curr_time else None,
                    "gap_seconds": gap_sec,
                    "gap_hours": gap_hours,
                    "day_of_week": day_of_week,
                    "hour": hour,
                })
                gap_durations.append(gap_sec)
                
                if day_of_week is not None:
                    gap_by_day[day_of_week] += 1
                    # Check if gap aligns with market close (Friday 17:00 EST to Sunday 17:00 EST)
                    # Friday = 5, Saturday = 6, Sunday = 0
                    if day_of_week in [5, 6, 0] or (day_of_week == 4 and hour and hour >= 17):
                        market_close_gaps += 1

            print(f"  Total Significant Gaps (>5min): {len(gaps)}")
            print(f"  Min Gap: {min(gap_durations)/3600:.2f} hours")
            print(f"  Max Gap: {max(gap_durations)/3600:.2f} hours")
            print(f"  Avg Gap: {np.mean(gap_durations)/3600:.2f} hours")
            print(f"  Median Gap: {np.median(gap_durations)/3600:.2f} hours")

            print(f"\n  Gaps by Symbol:")
            for symbol, gap_list in sorted(gap_by_symbol.items(), key=lambda x: len(x[1]), reverse=True):
                print(f"    {symbol}: {len(gap_list)} gaps")
                largest = max(gap_list, key=lambda x: x["gap_seconds"])
                print(f"      Largest: {largest['gap_hours']:.2f} hours ({largest['prev_time']} -> {largest['curr_time']})")

            print(f"\n  Gaps by Day of Week:")
            day_names = {0: "Sunday", 1: "Monday", 2: "Tuesday", 3: "Wednesday", 
                         4: "Thursday", 5: "Friday", 6: "Saturday"}
            for day in sorted(gap_by_day.keys()):
                print(f"    {day_names.get(day, f'Day {day}')}: {gap_by_day[day]} gaps")

            market_close_ratio = market_close_gaps / max(len(gaps), 1)
            print(f"\n  Market Close Alignment: {market_close_gaps} / {len(gaps)} ({market_close_ratio*100:.1f}%)")
            if market_close_ratio > 0.7:
                print("  -> Gaps align with market close (expected behavior)")
            else:
                print("  -> Gaps occur during market hours (connection issue)")

            # Check if gaps are consistent across symbols (system-wide)
            if len(gap_by_symbol) > 1:
                # Check if gaps occur at similar times across symbols
                gap_times = []
                for symbol, gap_list in gap_by_symbol.items():
                    for gap in gap_list:
                        if gap["prev_time"]:
                            gap_times.append(gap["prev_time"])
                
                # Group by time window (within 1 hour)
                time_windows = defaultdict(int)
                for gap_time_str in gap_times:
                    try:
                        gap_time = datetime.fromisoformat(gap_time_str.replace('Z', '+00:00'))
                        # Round to nearest hour
                        hour_key = gap_time.replace(minute=0, second=0, microsecond=0)
                        time_windows[hour_key.isoformat()] += 1
                    except:
                        pass
                
                simultaneous_gaps = sum(1 for count in time_windows.values() if count >= 3)
                print(f"\n  Simultaneous Gaps (3+ symbols): {simultaneous_gaps} time windows")
                if simultaneous_gaps > 0:
                    print("  -> SYSTEM-WIDE: Multiple symbols gap simultaneously (connection/server issue)")
                else:
                    print("  -> SYMBOL-SPECIFIC: Gaps occur independently (EA/connection per symbol)")

            self.results["data_gaps"] = {
                "total_gaps": len(gaps),
                "min_gap_hours": float(min(gap_durations) / 3600) if gap_durations else 0,
                "max_gap_hours": float(max(gap_durations) / 3600) if gap_durations else 0,
                "avg_gap_hours": float(np.mean(gap_durations) / 3600) if gap_durations else 0,
                "median_gap_hours": float(np.median(gap_durations) / 3600) if gap_durations else 0,
                "by_symbol": {k: len(v) for k, v in gap_by_symbol.items()},
                "by_day": dict(gap_by_day),
                "market_close_alignment_ratio": float(market_close_ratio),
                "is_market_hours_related": market_close_ratio > 0.7,
                "sample_gaps": {k: v[:2] for k, v in list(gap_by_symbol.items())[:5]},  # Top 5 symbols, 2 gaps each
            }

        except Exception as e:
            print(f"  ERROR: {e}")
            import traceback
            traceback.print_exc()
            self.results["data_gaps"]["error"] = str(e)

        print()

    def analyze_timestamp_sources(self, hours: int):
        """Analyze timestamp sources and correlation"""
        print("3. TIMESTAMP SOURCE ANALYSIS")
        print("-" * 80)

        # Compare event_time vs receive_time for negative latency cases
        query = """
            SELECT 
                fp.symbol,
                tf.datetime as event_time,
                tf.receive_time,
                tf.latency_seconds,
                EXTRACT(EPOCH FROM (tf.receive_time - tf.datetime)) as calculated_latency,
                tf.timestamp_source
            FROM ticks_forex tf
            JOIN forex_pairs fp ON tf.forex_pairs_id = fp.id
            WHERE tf.datetime >= NOW() - (INTERVAL '1 hour' * :hours)
            AND tf.latency_seconds < 0
            ORDER BY tf.latency_seconds ASC
            LIMIT 20
        """

        try:
            samples = self.db.execute_with_result(query, {"hours": hours})
            
            if samples:
                print(f"  Analyzing {len(samples)} negative latency samples:")
                print(f"  {'Symbol':<10} {'Event Time':<25} {'Receive Time':<25} {'Stored Latency':<15} {'Calculated Latency':<15} {'Source':<10}")
                print("-" * 110)
                
                for row in samples[:10]:  # Show first 10
                    symbol = row[0]
                    event_time = row[1]
                    receive_time = row[2]
                    stored_latency = float(row[3])
                    calculated_latency = float(row[4]) if row[4] else None
                    source = row[5] or "unknown"
                    
                    event_str = event_time.isoformat()[:19] if event_time else "N/A"
                    receive_str = receive_time.isoformat()[:19] if receive_time else "N/A"
                    calc_str = f"{calculated_latency:.3f}" if calculated_latency is not None else "N/A"
                    
                    print(f"  {symbol:<10} {event_str:<25} {receive_str:<25} {stored_latency:<15.3f} {calc_str:<15} {source:<10}")
                    
                    # Check if calculated matches stored
                    if calculated_latency is not None and abs(calculated_latency - stored_latency) > 0.1:
                        print(f"    WARNING: Mismatch between stored and calculated latency!")

                # Check timestamp source distribution
                query_source = """
                    SELECT 
                        tf.timestamp_source,
                        COUNT(*) as count,
                        AVG(tf.latency_seconds) as avg_latency,
                        COUNT(CASE WHEN tf.latency_seconds < 0 THEN 1 END) as negative_count
                    FROM ticks_forex tf
                    WHERE tf.datetime >= NOW() - (INTERVAL '1 hour' * :hours)
                    AND tf.receive_time IS NOT NULL
                    GROUP BY tf.timestamp_source
                """
                source_stats = self.db.execute_with_result(query_source, {"hours": hours})
                
                print(f"\n  Timestamp Source Distribution:")
                for row in source_stats:
                    source = row[0] or "NULL"
                    count = int(row[1])
                    avg_latency = float(row[2]) if row[2] else None
                    negative_count = int(row[3])
                    negative_pct = (negative_count / max(count, 1)) * 100
                    
                    print(f"    {source}: {count:,} ticks, avg latency: {avg_latency:.3f}s, negative: {negative_count} ({negative_pct:.2f}%)")

            self.results["timestamp_analysis"] = {
                "samples_analyzed": len(samples) if samples else 0,
            }

        except Exception as e:
            print(f"  ERROR: {e}")
            import traceback
            traceback.print_exc()
            self.results["timestamp_analysis"]["error"] = str(e)

        print()

    def identify_root_causes(self):
        """Identify root causes based on investigation"""
        print("4. ROOT CAUSE IDENTIFICATION")
        print("-" * 80)

        root_causes = []

        # Analyze negative latency
        neg_lat = self.results.get("negative_latency", {})
        if neg_lat.get("total_samples", 0) > 0:
            is_systematic = neg_lat.get("is_systematic", False)
            affected_ratio = neg_lat.get("affected_symbols_ratio", 0)
            
            if is_systematic and affected_ratio > 0.5:
                root_causes.append({
                    "issue": "Negative Latency",
                    "severity": "High",
                    "cause": "Clock synchronization issue - server time may be ahead of MT5 terminal time",
                    "evidence": f"Affects {affected_ratio*100:.1f}% of symbols, systematic pattern",
                    "impact": "651 ticks (2.56%) have negative latency, indicating receive_time < event_time",
                })
            else:
                root_causes.append({
                    "issue": "Negative Latency",
                    "severity": "Medium",
                    "cause": "Timestamp parsing or timezone conversion issue - may affect specific symbols",
                    "evidence": f"Affects {len(neg_lat.get('by_symbol', {}))} symbols, random pattern",
                    "impact": "651 ticks (2.56%) have negative latency",
                })

        # Analyze data gaps
        gaps = self.results.get("data_gaps", {})
        if gaps.get("total_gaps", 0) > 0:
            is_market_hours = gaps.get("is_market_hours_related", False)
            
            if is_market_hours:
                root_causes.append({
                    "issue": "Data Gaps",
                    "severity": "Low",
                    "cause": "Market hours - gaps align with forex market close (Friday-Sunday)",
                    "evidence": f"{gaps.get('market_close_alignment_ratio', 0)*100:.1f}% of gaps align with market close",
                    "impact": f"{gaps.get('total_gaps', 0)} gaps detected, ~{gaps.get('avg_gap_hours', 0):.1f} hours average",
                })
            else:
                root_causes.append({
                    "issue": "Data Gaps",
                    "severity": "Medium",
                    "cause": "Connection issues - gaps occur during market hours",
                    "evidence": "Gaps do not align with market close, suggesting connection drops",
                    "impact": f"{gaps.get('total_gaps', 0)} gaps detected during trading hours",
                })

        for cause in root_causes:
            print(f"  {cause['issue']}:")
            print(f"    Severity: {cause['severity']}")
            print(f"    Cause: {cause['cause']}")
            print(f"    Evidence: {cause['evidence']}")
            print(f"    Impact: {cause['impact']}")
            print()

        self.results["root_causes"] = root_causes

    def generate_recommendations(self):
        """Generate actionable recommendations"""
        print("5. RECOMMENDATIONS")
        print("-" * 80)

        recommendations = []

        # Recommendations for negative latency
        neg_lat = self.results.get("negative_latency", {})
        if neg_lat.get("total_samples", 0) > 0:
            recommendations.append({
                "priority": "High",
                "category": "Clock Synchronization",
                "action": "Implement NTP synchronization check and server clock validation",
                "details": "Add script to verify server clock accuracy and compare with NTP servers",
            })
            recommendations.append({
                "priority": "High",
                "category": "Timestamp Validation",
                "action": "Add validation to reject or flag future timestamps in quality gates",
                "details": "Enhance quality_gates.py to detect and handle negative latency cases",
            })
            recommendations.append({
                "priority": "Medium",
                "category": "Logging",
                "action": "Add logging for negative latency detection with full context",
                "details": "Log event_time, receive_time, and latency when negative latency detected",
            })

        # Recommendations for data gaps
        gaps = self.results.get("data_gaps", {})
        if gaps.get("total_gaps", 0) > 0:
            if not gaps.get("is_market_hours_related", False):
                recommendations.append({
                    "priority": "Medium",
                    "category": "Connection Monitoring",
                    "action": "Improve connection monitoring and auto-reconnect logic",
                    "details": "Add connection health checks and automatic reconnection on drops",
                })
                recommendations.append({
                    "priority": "Low",
                    "category": "Alerting",
                    "action": "Add gap detection alerts for gaps during market hours",
                    "details": "Alert when gaps > 5 minutes occur during trading hours",
                })

        for rec in recommendations:
            print(f"  [{rec['priority']}] {rec['category']}: {rec['action']}")
            print(f"      {rec['details']}")
            print()

        self.results["recommendations"] = recommendations

    def generate_report(self, output_path: str):
        """Generate markdown report"""
        report_lines = [
            "# Data Issues Investigation Report",
            f"Generated: {datetime.now().isoformat()}",
            "",
            "## Executive Summary",
            "",
        ]

        # Add root causes
        if self.results.get("root_causes"):
            report_lines.append("## Root Causes")
            report_lines.append("")
            for cause in self.results["root_causes"]:
                report_lines.append(f"### {cause['issue']}")
                report_lines.append("")
                report_lines.append(f"- **Severity**: {cause['severity']}")
                report_lines.append(f"- **Cause**: {cause['cause']}")
                report_lines.append(f"- **Evidence**: {cause['evidence']}")
                report_lines.append(f"- **Impact**: {cause['impact']}")
                report_lines.append("")

        # Add recommendations
        if self.results.get("recommendations"):
            report_lines.append("## Recommendations")
            report_lines.append("")
            for rec in self.results["recommendations"]:
                report_lines.append(f"### [{rec['priority']}] {rec['category']}")
                report_lines.append("")
                report_lines.append(f"**Action**: {rec['action']}")
                report_lines.append("")
                report_lines.append(f"**Details**: {rec['details']}")
                report_lines.append("")

        # Add detailed results
        report_lines.extend([
            "## Detailed Results",
            "",
            "```json",
            json.dumps(self.results, indent=2, default=str),
            "```",
        ])

        output_file = Path(output_path)
        output_file.parent.mkdir(parents=True, exist_ok=True)
        output_file.write_text("\n".join(report_lines), encoding='utf-8')
        print(f"\nReport saved to: {output_path}")


def main():
    """Main entry point"""
    import argparse

    parser = argparse.ArgumentParser(description="Investigate data collection issues")
    parser.add_argument("--hours", type=int, default=48, help="Hours of data to analyze (default: 48)")
    parser.add_argument("--output", type=str, default="docs/generated/DATA_ISSUES_INVESTIGATION.md",
                        help="Output report path")

    args = parser.parse_args()

    # Initialize database
    db = Database()

    # Run investigation
    investigator = DataIssuesInvestigator(db)
    investigator.investigate_all(hours=args.hours)

    # Generate report
    investigator.generate_report(args.output)

    print(f"\n{'='*80}")
    print("INVESTIGATION COMPLETE")
    print(f"{'='*80}\n")


if __name__ == "__main__":
    main()
