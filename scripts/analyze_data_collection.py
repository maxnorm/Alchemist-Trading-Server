#!/usr/bin/env python
"""
Comprehensive analysis of tick data collection pipeline correctness.

This script analyzes:
1. Data volume and coverage
2. Data quality metrics
3. Timestamp correctness
4. Price data validity
5. Gaps and anomalies
6. MT5 EA log analysis
"""

import os
import sys
import json
from datetime import datetime, timedelta
from pathlib import Path
from typing import Dict, List, Tuple, Optional
from collections import defaultdict
import statistics

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


class DataCollectionAnalyzer:
    """Comprehensive analysis of tick data collection"""

    def __init__(self, db: Database):
        self.db = db
        self.results = {
            "summary": {},
            "symbols": {},
            "quality_metrics": {},
            "timestamp_analysis": {},
            "price_analysis": {},
            "gaps_analysis": {},
            "anomalies": [],
            "mt5_log_analysis": {},
        }

    def analyze_all(self, hours: int = 24) -> Dict:
        """Run all analyses"""
        print(f"\n{'='*80}")
        print(f"DATA COLLECTION PIPELINE ANALYSIS")
        print(f"{'='*80}\n")
        print(f"Analyzing data from last {hours} hours...\n")

        # 1. Summary statistics
        self.analyze_summary(hours)

        # 2. Per-symbol analysis
        self.analyze_symbols(hours)

        # 3. Quality metrics
        self.analyze_quality_metrics(hours)

        # 4. Timestamp analysis
        self.analyze_timestamps(hours)

        # 5. Price analysis
        self.analyze_prices(hours)

        # 6. Gap analysis
        self.analyze_gaps(hours)

        # 7. Anomaly detection
        self.detect_anomalies(hours)

        return self.results

    def analyze_summary(self, hours: int):
        """Overall summary statistics"""
        print("1. SUMMARY STATISTICS")
        print("-" * 80)

        query = """
            SELECT 
                COUNT(*) as total_ticks,
                COUNT(DISTINCT fp.symbol) as unique_symbols,
                MIN(tf.datetime) as earliest_tick,
                MAX(tf.datetime) as latest_tick,
                COUNT(CASE WHEN tf.is_stale = TRUE THEN 1 END) as stale_count,
                COUNT(CASE WHEN tf.receive_time IS NOT NULL THEN 1 END) as has_receive_time,
                AVG(tf.latency_seconds) as avg_latency,
                PERCENTILE_CONT(0.5) WITHIN GROUP (ORDER BY tf.latency_seconds) as median_latency,
                PERCENTILE_CONT(0.95) WITHIN GROUP (ORDER BY tf.latency_seconds) as p95_latency
            FROM ticks_forex tf
            JOIN forex_pairs fp ON tf.forex_pairs_id = fp.id
            WHERE tf.datetime >= NOW() - (INTERVAL '1 hour' * :hours)
        """

        try:
            result = self.db.execute_with_result(query, {"hours": hours})
            if result:
                row = result[0]
                self.results["summary"] = {
                    "total_ticks": int(row[0]) if row[0] else 0,
                    "unique_symbols": int(row[1]) if row[1] else 0,
                    "earliest_tick": row[2].isoformat() if row[2] else None,
                    "latest_tick": row[3].isoformat() if row[3] else None,
                    "stale_count": int(row[4]) if row[4] else 0,
                    "has_receive_time": int(row[5]) if row[5] else 0,
                    "avg_latency_seconds": float(row[6]) if row[6] else None,
                    "median_latency_seconds": float(row[7]) if row[7] else None,
                    "p95_latency_seconds": float(row[8]) if row[8] else None,
                }

                print(f"  Total Ticks: {self.results['summary']['total_ticks']:,}")
                print(f"  Unique Symbols: {self.results['summary']['unique_symbols']}")
                print(f"  Time Range: {self.results['summary']['earliest_tick']} to {self.results['summary']['latest_tick']}")
                print(f"  Stale Ticks: {self.results['summary']['stale_count']:,} ({self.results['summary']['stale_count']/max(self.results['summary']['total_ticks'],1)*100:.2f}%)")
                print(f"  With Receive Time: {self.results['summary']['has_receive_time']:,} ({self.results['summary']['has_receive_time']/max(self.results['summary']['total_ticks'],1)*100:.2f}%)")
                if self.results['summary']['avg_latency_seconds'] is not None:
                    print(f"  Avg Latency: {self.results['summary']['avg_latency_seconds']:.3f}s")
                if self.results['summary']['median_latency_seconds'] is not None:
                    print(f"  Median Latency: {self.results['summary']['median_latency_seconds']:.3f}s")
                if self.results['summary']['p95_latency_seconds'] is not None:
                    print(f"  P95 Latency: {self.results['summary']['p95_latency_seconds']:.3f}s")
        except Exception as e:
            print(f"  ERROR: {e}")
            self.results["summary"]["error"] = str(e)

        print()

    def analyze_symbols(self, hours: int):
        """Per-symbol statistics"""
        print("2. PER-SYMBOL ANALYSIS")
        print("-" * 80)

        query = """
            SELECT 
                fp.symbol,
                COUNT(*) as tick_count,
                MIN(tf.datetime) as first_tick,
                MAX(tf.datetime) as last_tick,
                COUNT(CASE WHEN tf.is_stale = TRUE THEN 1 END) as stale_count,
                AVG(tf.ask - tf.bid) as avg_spread,
                MIN(tf.ask - tf.bid) as min_spread,
                MAX(tf.ask - tf.bid) as max_spread,
                AVG(tf.latency_seconds) as avg_latency
            FROM ticks_forex tf
            JOIN forex_pairs fp ON tf.forex_pairs_id = fp.id
            WHERE tf.datetime >= NOW() - (INTERVAL '1 hour' * :hours)
            GROUP BY fp.symbol
            ORDER BY tick_count DESC
        """

        try:
            results = self.db.execute_with_result(query, {"hours": hours})
            symbols_data = {}

            print(f"{'Symbol':<10} {'Ticks':<12} {'Stale':<10} {'Avg Spread':<12} {'Avg Latency':<12}")
            print("-" * 80)

            for row in results:
                symbol = row[0]
                symbols_data[symbol] = {
                    "tick_count": int(row[1]),
                    "first_tick": row[2].isoformat() if row[2] else None,
                    "last_tick": row[3].isoformat() if row[3] else None,
                    "stale_count": int(row[4]) if row[4] else 0,
                    "avg_spread": float(row[5]) if row[5] else None,
                    "min_spread": float(row[6]) if row[6] else None,
                    "max_spread": float(row[7]) if row[7] else None,
                    "avg_latency": float(row[8]) if row[8] else None,
                }

                stale_pct = (symbols_data[symbol]["stale_count"] / max(symbols_data[symbol]["tick_count"], 1)) * 100
                avg_spread_str = f"{symbols_data[symbol]['avg_spread']:.6f}" if symbols_data[symbol]['avg_spread'] is not None else "N/A"
                avg_latency_str = f"{symbols_data[symbol]['avg_latency']:.3f}" if symbols_data[symbol]['avg_latency'] is not None else "N/A"
                print(f"{symbol:<10} {symbols_data[symbol]['tick_count']:<12,} {stale_pct:<9.1f}% {avg_spread_str:<12} {avg_latency_str:<12}")

            self.results["symbols"] = symbols_data
        except Exception as e:
            print(f"  ERROR: {e}")
            self.results["symbols"]["error"] = str(e)

        print()

    def analyze_quality_metrics(self, hours: int):
        """Data quality metrics"""
        print("3. QUALITY METRICS")
        print("-" * 80)

        # Check for invalid prices
        query_invalid = """
            SELECT COUNT(*) 
            FROM ticks_forex tf
            WHERE tf.datetime >= NOW() - (INTERVAL '1 hour' * :hours)
            AND (tf.bid <= 0 OR tf.ask <= 0 OR tf.ask <= tf.bid)
        """

        # Check for extreme spreads
        query_extreme_spread = """
            SELECT COUNT(*)
            FROM ticks_forex tf
            JOIN forex_pairs fp ON tf.forex_pairs_id = fp.id
            WHERE tf.datetime >= NOW() - (INTERVAL '1 hour' * :hours)
            AND (tf.ask - tf.bid) > 0.01
        """

        # Check for duplicate timestamps (same symbol, same datetime)
        query_duplicates = """
            SELECT fp.symbol, tf.datetime, COUNT(*) as cnt
            FROM ticks_forex tf
            JOIN forex_pairs fp ON tf.forex_pairs_id = fp.id
            WHERE tf.datetime >= NOW() - (INTERVAL '1 hour' * :hours)
            GROUP BY fp.symbol, tf.datetime
            HAVING COUNT(*) > 1
            ORDER BY cnt DESC
            LIMIT 10
        """

        try:
            invalid_count = self.db.execute_with_result(query_invalid, {"hours": hours})[0][0]
            extreme_spread_count = self.db.execute_with_result(query_extreme_spread, {"hours": hours})[0][0]
            duplicates = self.db.execute_with_result(query_duplicates, {"hours": hours})

            self.results["quality_metrics"] = {
                "invalid_prices": int(invalid_count),
                "extreme_spreads": int(extreme_spread_count),
                "duplicate_timestamps": len(duplicates),
                "duplicate_examples": [
                    {"symbol": row[0], "datetime": row[1].isoformat(), "count": int(row[2])}
                    for row in duplicates[:5]
                ],
            }

            total = self.results["summary"].get("total_ticks", 1)
            print(f"  Invalid Prices (bid<=0, ask<=0, ask<=bid): {invalid_count:,} ({invalid_count/max(total,1)*100:.2f}%)")
            print(f"  Extreme Spreads (>100 pips): {extreme_spread_count:,} ({extreme_spread_count/max(total,1)*100:.2f}%)")
            print(f"  Duplicate Timestamps: {len(duplicates):,} unique cases")
            if duplicates:
                print(f"  Top Duplicate Examples:")
                for dup in self.results["quality_metrics"]["duplicate_examples"][:5]:
                    print(f"    {dup['symbol']} @ {dup['datetime']}: {dup['count']} ticks")

        except Exception as e:
            print(f"  ERROR: {e}")
            self.results["quality_metrics"]["error"] = str(e)

        print()

    def analyze_timestamps(self, hours: int):
        """Timestamp correctness analysis"""
        print("4. TIMESTAMP ANALYSIS")
        print("-" * 80)

        # Check for future timestamps
        query_future = """
            SELECT COUNT(*)
            FROM ticks_forex tf
            WHERE tf.datetime >= NOW() - (INTERVAL '1 hour' * :hours)
            AND tf.datetime > NOW() + INTERVAL '1 minute'
        """

        # Check for very old timestamps
        query_old = """
            SELECT COUNT(*)
            FROM ticks_forex tf
            WHERE tf.datetime >= NOW() - (INTERVAL '1 hour' * :hours)
            AND tf.datetime < NOW() - INTERVAL '7 days'
        """

        # Analyze receive_time vs datetime
        query_latency_dist = """
            SELECT 
                COUNT(*) as total,
                COUNT(CASE WHEN tf.latency_seconds < 0 THEN 1 END) as negative_latency,
                COUNT(CASE WHEN tf.latency_seconds > 60 THEN 1 END) as high_latency,
                COUNT(CASE WHEN tf.latency_seconds BETWEEN 0 AND 1 THEN 1 END) as low_latency,
                COUNT(CASE WHEN tf.latency_seconds BETWEEN 1 AND 5 THEN 1 END) as medium_latency
            FROM ticks_forex tf
            WHERE tf.datetime >= NOW() - (INTERVAL '1 hour' * :hours)
            AND tf.receive_time IS NOT NULL
        """

        try:
            future_count = self.db.execute_with_result(query_future, {"hours": hours})[0][0]
            old_count = self.db.execute_with_result(query_old, {"hours": hours})[0][0]
            latency_dist = self.db.execute_with_result(query_latency_dist, {"hours": hours})[0]

            self.results["timestamp_analysis"] = {
                "future_timestamps": int(future_count),
                "very_old_timestamps": int(old_count),
                "latency_distribution": {
                    "total_with_receive_time": int(latency_dist[0]),
                    "negative_latency": int(latency_dist[1]),
                    "high_latency_>60s": int(latency_dist[2]),
                    "low_latency_<1s": int(latency_dist[3]),
                    "medium_latency_1-5s": int(latency_dist[4]),
                },
            }

            print(f"  Future Timestamps (>1min ahead): {future_count:,}")
            print(f"  Very Old Timestamps (>7 days old): {old_count:,}")
            print(f"  Latency Distribution:")
            if latency_dist[0] > 0:
                print(f"    Total with receive_time: {latency_dist[0]:,}")
                print(f"    Negative Latency: {latency_dist[1]:,} ({latency_dist[1]/max(latency_dist[0],1)*100:.2f}%)")
                print(f"    High Latency (>60s): {latency_dist[2]:,} ({latency_dist[2]/max(latency_dist[0],1)*100:.2f}%)")
                print(f"    Low Latency (<1s): {latency_dist[3]:,} ({latency_dist[3]/max(latency_dist[0],1)*100:.2f}%)")
                print(f"    Medium Latency (1-5s): {latency_dist[4]:,} ({latency_dist[4]/max(latency_dist[0],1)*100:.2f}%)")

        except Exception as e:
            print(f"  ERROR: {e}")
            self.results["timestamp_analysis"]["error"] = str(e)

        print()

    def analyze_prices(self, hours: int):
        """Price data validity"""
        print("5. PRICE ANALYSIS")
        print("-" * 80)

        query = """
            SELECT 
                fp.symbol,
                MIN(tf.bid) as min_bid,
                MAX(tf.bid) as max_bid,
                MIN(tf.ask) as min_ask,
                MAX(tf.ask) as max_ask,
                AVG(tf.ask - tf.bid) as avg_spread,
                STDDEV(tf.ask - tf.bid) as spread_stddev,
                0 as spread_jumps
            FROM ticks_forex tf
            JOIN forex_pairs fp ON tf.forex_pairs_id = fp.id
            WHERE tf.datetime >= NOW() - (INTERVAL '1 hour' * :hours)
            GROUP BY fp.symbol
            ORDER BY fp.symbol
        """

        try:
            results = self.db.execute_with_result(query, {"hours": hours})
            price_data = {}

            print(f"{'Symbol':<10} {'Bid Range':<20} {'Ask Range':<20} {'Avg Spread':<12} {'Spread StdDev':<12}")
            print("-" * 80)

            for row in results:
                symbol = row[0]
                price_data[symbol] = {
                    "min_bid": float(row[1]) if row[1] else None,
                    "max_bid": float(row[2]) if row[2] else None,
                    "min_ask": float(row[3]) if row[3] else None,
                    "max_ask": float(row[4]) if row[4] else None,
                    "avg_spread": float(row[5]) if row[5] else None,
                    "spread_stddev": float(row[6]) if row[6] else None,
                }

                bid_range = f"{price_data[symbol]['min_bid']:.5f}-{price_data[symbol]['max_bid']:.5f}" if price_data[symbol]['min_bid'] is not None else "N/A"
                ask_range = f"{price_data[symbol]['min_ask']:.5f}-{price_data[symbol]['max_ask']:.5f}" if price_data[symbol]['min_ask'] is not None else "N/A"
                avg_spread_str = f"{price_data[symbol]['avg_spread']:.6f}" if price_data[symbol]['avg_spread'] is not None else "N/A"
                spread_stddev_str = f"{price_data[symbol]['spread_stddev']:.6f}" if price_data[symbol]['spread_stddev'] is not None else "N/A"
                print(f"{symbol:<10} {bid_range:<20} {ask_range:<20} {avg_spread_str:<12} {spread_stddev_str:<12}")

            self.results["price_analysis"] = price_data
        except Exception as e:
            print(f"  ERROR: {e}")
            self.results["price_analysis"]["error"] = str(e)

        print()

    def analyze_gaps(self, hours: int):
        """Detect data gaps"""
        print("6. GAP ANALYSIS")
        print("-" * 80)

        # Find symbols with significant gaps (>5 minutes)
        query_gaps = """
            WITH tick_intervals AS (
                SELECT 
                    fp.symbol,
                    tf.datetime,
                    LAG(tf.datetime) OVER (PARTITION BY fp.symbol ORDER BY tf.datetime) as prev_datetime,
                    EXTRACT(EPOCH FROM (tf.datetime - LAG(tf.datetime) OVER (PARTITION BY fp.symbol ORDER BY tf.datetime))) as gap_seconds
                FROM ticks_forex tf
                JOIN forex_pairs fp ON tf.forex_pairs_id = fp.id
                WHERE tf.datetime >= NOW() - (INTERVAL '1 hour' * :hours)
            )
            SELECT 
                symbol,
                COUNT(*) as gap_count,
                MAX(gap_seconds) as max_gap,
                AVG(gap_seconds) as avg_gap,
                PERCENTILE_CONT(0.95) WITHIN GROUP (ORDER BY gap_seconds) as p95_gap
            FROM tick_intervals
            WHERE gap_seconds > 300  -- 5 minutes
            GROUP BY symbol
            ORDER BY gap_count DESC
            LIMIT 10
        """

        try:
            gaps = self.db.execute_with_result(query_gaps, {"hours": hours})
            gaps_data = {}

            if gaps:
                print(f"{'Symbol':<10} {'Gap Count':<12} {'Max Gap (s)':<12} {'Avg Gap (s)':<12} {'P95 Gap (s)':<12}")
                print("-" * 80)

                for row in gaps:
                    symbol = row[0]
                    gaps_data[symbol] = {
                        "gap_count": int(row[1]),
                        "max_gap_seconds": float(row[2]) if row[2] else None,
                        "avg_gap_seconds": float(row[3]) if row[3] else None,
                        "p95_gap_seconds": float(row[4]) if row[4] else None,
                    }
                    print(f"{symbol:<10} {gaps_data[symbol]['gap_count']:<12} {gaps_data[symbol]['max_gap_seconds']:<12.1f} {gaps_data[symbol]['avg_gap_seconds']:<12.1f} {gaps_data[symbol]['p95_gap_seconds']:<12.1f}")
            else:
                print("  No significant gaps (>5 minutes) detected")

            self.results["gaps_analysis"] = gaps_data
        except Exception as e:
            print(f"  ERROR: {e}")
            self.results["gaps_analysis"]["error"] = str(e)

        print()

    def detect_anomalies(self, hours: int):
        """Detect anomalies in the data"""
        print("7. ANOMALY DETECTION")
        print("-" * 80)

        anomalies = []

        # Check for price jumps > 1% (using subquery to avoid window function in WHERE)
        query_price_jumps = """
            WITH price_changes AS (
                SELECT 
                    fp.symbol,
                    tf.datetime,
                    tf.bid,
                    tf.ask,
                    LAG(tf.bid) OVER (PARTITION BY fp.symbol ORDER BY tf.datetime) as prev_bid,
                    ABS((tf.bid - LAG(tf.bid) OVER (PARTITION BY fp.symbol ORDER BY tf.datetime)) / NULLIF(LAG(tf.bid) OVER (PARTITION BY fp.symbol ORDER BY tf.datetime), 0)) * 100 as bid_change_pct
                FROM ticks_forex tf
                JOIN forex_pairs fp ON tf.forex_pairs_id = fp.id
                WHERE tf.datetime >= NOW() - (INTERVAL '1 hour' * :hours)
            )
            SELECT symbol, datetime, bid, ask, prev_bid, bid_change_pct
            FROM price_changes
            WHERE bid_change_pct > 1.0 AND prev_bid IS NOT NULL
            ORDER BY bid_change_pct DESC
            LIMIT 10
        """

        try:
            price_jumps = self.db.execute_with_result(query_price_jumps, {"hours": hours})
            if price_jumps:
                print(f"  Large Price Jumps (>1%): {len(price_jumps)}")
                for row in price_jumps[:5]:
                    anomaly = {
                        "type": "large_price_jump",
                        "symbol": row[0],
                        "datetime": row[1].isoformat() if row[1] else None,
                        "bid": float(row[2]),
                        "prev_bid": float(row[3]) if row[3] else None,
                        "change_pct": float(row[4]) if row[4] else None,
                    }
                    anomalies.append(anomaly)
                    print(f"    {anomaly['symbol']} @ {anomaly['datetime']}: {anomaly['change_pct']:.2f}% change")
            else:
                print("  No large price jumps detected")

            self.results["anomalies"] = anomalies
        except Exception as e:
            print(f"  ERROR: {e}")
            self.results["anomalies"] = [{"error": str(e)}]

        print()

    def analyze_mt5_logs(self, log_dir: str):
        """Analyze MT5 EA logs"""
        print("8. MT5 EA LOG ANALYSIS")
        print("-" * 80)

        log_path = Path(log_dir)
        if not log_path.exists():
            print(f"  WARNING: Log directory not found: {log_dir}")
            return

        # Find most recent log file
        log_files = sorted(log_path.glob("*.log"), key=lambda x: x.stat().st_mtime, reverse=True)
        if not log_files:
            print("  No log files found")
            return

        recent_log = log_files[0]
        print(f"  Analyzing: {recent_log.name}")

        stats = {
            "total_lines": 0,
            "auth_success": 0,
            "auth_failures": 0,
            "tick_sent": 0,
            "errors": [],
            "symbols": set(),
        }

        try:
            # MT5 logs are UTF-16 encoded
            with open(recent_log, 'r', encoding='utf-16-le', errors='ignore') as f:
                for line in f:
                    stats["total_lines"] += 1
                    line_lower = line.lower()
                    line_stripped = line.strip()
                    
                    # MT5 logs are tab-separated: CODE TAB TIME TAB EA_NAME TAB MESSAGE
                    # Extract the message part (after last tab)
                    parts = line.split('\t')
                    message = parts[-1] if len(parts) > 1 else line_stripped
                    message_lower = message.lower()

                    # Check for authentication success
                    if "successful authentification" in message_lower:
                        stats["auth_success"] += 1
                    elif '"auth_status": 0' in message or '"auth_status":0' in message:
                        stats["auth_success"] += 1
                    
                    # Check for authentication failures
                    if "failed authentification" in message_lower:
                        stats["auth_failures"] += 1
                    elif '"auth_status": -1' in message or '"auth_status":-1' in message:
                        stats["auth_failures"] += 1
                    
                    # Check for tick messages - look for JSON with symbol field
                    if ("send_msg" in message_lower or "[ea] send_msg" in message_lower) and "sending message" in message_lower:
                        # Look for JSON pattern with symbol (tick data, not auth)
                        if '"symbol"' in message and '"datetime"' in message and '"ask"' in message:
                            stats["tick_sent"] += 1
                            # Extract symbol from JSON
                            symbol = None
                            # Pattern: "symbol":"SYMBOL"
                            if '"symbol":"' in message:
                                try:
                                    symbol_start = message.find('"symbol":"') + 10
                                    symbol_end = message.find('"', symbol_start)
                                    if symbol_end > symbol_start:
                                        symbol = message[symbol_start:symbol_end]
                                except:
                                    pass
                            if symbol and len(symbol) >= 3:  # Valid symbol should be at least 3 chars
                                stats["symbols"].add(symbol.upper())
                    
                    # Check for errors (but exclude authentication failures we already counted)
                    if ("error" in message_lower or "failed" in message_lower) and "authentification" not in message_lower:
                        if len(stats["errors"]) < 20:  # Keep last 20 errors
                            stats["errors"].append(message[:200])  # Truncate long lines

            stats["symbols"] = sorted(list(stats["symbols"]))

            print(f"  Total Lines: {stats['total_lines']:,}")
            print(f"  Auth Success: {stats['auth_success']}")
            print(f"  Auth Failures: {stats['auth_failures']}")
            print(f"  Ticks Sent: {stats['tick_sent']:,}")
            print(f"  Symbols: {', '.join(stats['symbols'][:10])}")
            if len(stats['symbols']) > 10:
                print(f"    ... and {len(stats['symbols']) - 10} more")
            if stats["errors"]:
                print(f"  Errors Found: {len(stats['errors'])}")
                print(f"  Sample Errors:")
                for err in stats["errors"][:5]:
                    print(f"    {err[:100]}")

            self.results["mt5_log_analysis"] = {
                "log_file": recent_log.name,
                "total_lines": stats["total_lines"],
                "auth_success": stats["auth_success"],
                "auth_failures": stats["auth_failures"],
                "tick_sent": stats["tick_sent"],
                "symbols": stats["symbols"],
                "error_count": len(stats["errors"]),
                "sample_errors": stats["errors"][:10],
            }

        except Exception as e:
            print(f"  ERROR reading log: {e}")
            self.results["mt5_log_analysis"]["error"] = str(e)

        print()

    def generate_report(self, output_path: str):
        """Generate markdown report"""
        report_lines = [
            "# Data Collection Pipeline Analysis Report",
            f"Generated: {datetime.now().isoformat()}",
            "",
            "## Executive Summary",
            "",
            f"- **Total Ticks Collected**: {self.results['summary'].get('total_ticks', 0):,}",
            f"- **Unique Symbols**: {self.results['summary'].get('unique_symbols', 0)}",
            f"- **Time Range**: {self.results['summary'].get('earliest_tick', 'N/A')} to {self.results['summary'].get('latest_tick', 'N/A')}",
            f"- **Stale Ticks**: {self.results['summary'].get('stale_count', 0):,} ({self.results['summary'].get('stale_count', 0)/max(self.results['summary'].get('total_ticks', 1), 1)*100:.2f}%)",
            "",
            "## Quality Metrics",
            "",
            f"- **Invalid Prices**: {self.results['quality_metrics'].get('invalid_prices', 0):,}",
            f"- **Extreme Spreads**: {self.results['quality_metrics'].get('extreme_spreads', 0):,}",
            f"- **Duplicate Timestamps**: {self.results['quality_metrics'].get('duplicate_timestamps', 0):,}",
            "",
            "## Timestamp Analysis",
            "",
            f"- **Future Timestamps**: {self.results['timestamp_analysis'].get('future_timestamps', 0):,}",
            f"- **Very Old Timestamps**: {self.results['timestamp_analysis'].get('very_old_timestamps', 0):,}",
            "",
            "## MT5 EA Log Analysis",
            "",
        ]

        if "mt5_log_analysis" in self.results:
            mt5 = self.results["mt5_log_analysis"]
            report_lines.extend([
                f"- **Log File**: {mt5.get('log_file', 'N/A')}",
                f"- **Auth Success**: {mt5.get('auth_success', 0)}",
                f"- **Auth Failures**: {mt5.get('auth_failures', 0)}",
                f"- **Ticks Sent**: {mt5.get('tick_sent', 0):,}",
                f"- **Symbols**: {len(mt5.get('symbols', []))}",
                "",
            ])

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

    parser = argparse.ArgumentParser(description="Analyze tick data collection pipeline")
    parser.add_argument("--hours", type=int, default=24, help="Hours of data to analyze (default: 24)")
    parser.add_argument("--mt5-logs", type=str, help="Path to MT5 EA logs directory")
    parser.add_argument("--output", type=str, default="docs/generated/DATA_COLLECTION_ANALYSIS.md",
                        help="Output report path (default: docs/generated/DATA_COLLECTION_ANALYSIS.md)")

    args = parser.parse_args()

    # Initialize database
    db = Database()

    # Run analysis
    analyzer = DataCollectionAnalyzer(db)
    analyzer.analyze_all(hours=args.hours)

    # Analyze MT5 logs if provided
    if args.mt5_logs:
        analyzer.analyze_mt5_logs(args.mt5_logs)

    # Generate report
    analyzer.generate_report(args.output)

    print(f"\n{'='*80}")
    print("ANALYSIS COMPLETE")
    print(f"{'='*80}\n")


if __name__ == "__main__":
    main()
