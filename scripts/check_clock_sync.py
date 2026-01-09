#!/usr/bin/env python
"""
Check server clock synchronization with NTP servers.

This script verifies:
1. Server clock accuracy
2. Time drift from NTP servers
3. Timezone configuration
4. Clock synchronization status
"""

import os
import sys
from datetime import datetime, timedelta
from pathlib import Path
import socket
import struct

# Add src to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '../src/trading_server/src'))

try:
    from utils.time_utils import get_utc_time
except ImportError:
    print("ERROR: Could not import time_utils module")
    sys.exit(1)


class ClockSyncChecker:
    """Check clock synchronization"""

    def __init__(self):
        self.results = {
            "server_time": None,
            "ntp_servers": [],
            "time_drift": {},
            "timezone_info": {},
            "recommendations": [],
        }

    def check_all(self):
        """Run all clock checks"""
        print(f"\n{'='*80}")
        print(f"CLOCK SYNCHRONIZATION CHECK")
        print(f"{'='*80}\n")

        # 1. Check server time
        self.check_server_time()

        # 2. Check NTP synchronization
        self.check_ntp_sync()

        # 3. Check timezone
        self.check_timezone()

        # 4. Generate recommendations
        self.generate_recommendations()

        return self.results

    def check_server_time(self):
        """Check server time"""
        print("1. SERVER TIME CHECK")
        print("-" * 80)

        try:
            server_time = get_utc_time()
            self.results["server_time"] = server_time.isoformat()

            print(f"  Server UTC Time: {server_time.isoformat()}")
            print(f"  Server Timestamp: {server_time.timestamp():.6f}")
            print(f"  Timezone: {server_time.tzinfo}")

        except Exception as e:
            print(f"  ERROR: {e}")
            self.results["server_time"] = {"error": str(e)}

        print()

    def ntp_time(self, host="pool.ntp.org", port=123, timeout=5):
        """Get time from NTP server"""
        try:
            # NTP protocol constants
            REFERENCE_TIME = 2208988800  # 1970-01-01 00:00:00
            NTP_PACKET_FORMAT = "!12I"
            NTP_DELTA = 2208988800  # 1970-01-01 00:00:00

            # Create NTP request packet
            client = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
            client.settimeout(timeout)

            # Send NTP request
            data = b'\x1b' + 47 * b'\0'
            client.sendto(data, (host, port))

            # Receive response
            data, address = client.recvfrom(1024)
            client.close()

            # Parse NTP response
            if data:
                unpacked = struct.unpack(NTP_PACKET_FORMAT, data[0:struct.calcsize(NTP_PACKET_FORMAT)])
                seconds = unpacked[10] - NTP_DELTA
                fraction = unpacked[11] / 2**32
                ntp_time = seconds + fraction
                return datetime.fromtimestamp(ntp_time, tz=None)
        except Exception as e:
            return None

    def check_ntp_sync(self):
        """Check synchronization with NTP servers"""
        print("2. NTP SYNCHRONIZATION CHECK")
        print("-" * 80)

        ntp_servers = [
            "pool.ntp.org",
            "time.google.com",
            "time.cloudflare.com",
            "time.windows.com",
        ]

        server_time = get_utc_time()
        successful_checks = 0
        total_drift = 0.0

        print(f"  Checking against NTP servers...")
        print(f"  {'Server':<25} {'Status':<15} {'NTP Time':<30} {'Drift (s)':<15}")
        print("-" * 85)

        for server in ntp_servers:
            try:
                ntp_time = self.ntp_time(server)
                if ntp_time:
                    # Make ntp_time timezone-aware (assume UTC)
                    from datetime import timezone
                    ntp_time_utc = ntp_time.replace(tzinfo=timezone.utc)
                    
                    # Calculate drift
                    drift_seconds = (server_time - ntp_time_utc).total_seconds()
                    total_drift += drift_seconds
                    successful_checks += 1

                    status = "OK" if abs(drift_seconds) < 1.0 else "WARNING"
                    print(f"  {server:<25} {status:<15} {ntp_time_utc.isoformat()[:19]:<30} {drift_seconds:>10.3f}")

                    self.results["ntp_servers"].append({
                        "server": server,
                        "ntp_time": ntp_time_utc.isoformat(),
                        "drift_seconds": drift_seconds,
                        "status": status,
                    })
                else:
                    print(f"  {server:<25} {'FAILED':<15} {'N/A':<30} {'N/A':<15}")
                    self.results["ntp_servers"].append({
                        "server": server,
                        "status": "FAILED",
                        "error": "Could not connect",
                    })
            except Exception as e:
                print(f"  {server:<25} {'ERROR':<15} {'N/A':<30} {'N/A':<15}")
                self.results["ntp_servers"].append({
                    "server": server,
                    "status": "ERROR",
                    "error": str(e),
                })

        if successful_checks > 0:
            avg_drift = total_drift / successful_checks
            self.results["time_drift"] = {
                "average_seconds": avg_drift,
                "successful_checks": successful_checks,
            }

            print(f"\n  Average Drift: {avg_drift:.3f} seconds")
            if abs(avg_drift) > 1.0:
                print(f"  WARNING: Server clock is {abs(avg_drift):.3f}s {'ahead' if avg_drift > 0 else 'behind'} NTP")
            elif abs(avg_drift) > 0.1:
                print(f"  INFO: Server clock is {abs(avg_drift):.3f}s {'ahead' if avg_drift > 0 else 'behind'} NTP (acceptable)")
            else:
                print(f"  OK: Server clock is well synchronized")
        else:
            print(f"\n  ERROR: Could not check any NTP servers")
            self.results["time_drift"] = {"error": "No successful NTP checks"}

        print()

    def check_timezone(self):
        """Check timezone configuration"""
        print("3. TIMEZONE CHECK")
        print("-" * 80)

        try:
            import time
            import os

            # System timezone
            if os.name == 'nt':  # Windows
                import winreg
                try:
                    key = winreg.OpenKey(winreg.HKEY_LOCAL_MACHINE, r"SYSTEM\CurrentControlSet\Control\TimeZoneInformation")
                    timezone_name = winreg.QueryValueEx(key, "TimeZoneKeyName")[0]
                    winreg.CloseKey(key)
                    print(f"  System Timezone: {timezone_name}")
                except:
                    print(f"  System Timezone: Could not determine")
            else:  # Unix-like
                try:
                    timezone_name = os.environ.get('TZ', 'Not set')
                    print(f"  System Timezone: {timezone_name}")
                except:
                    print(f"  System Timezone: Could not determine")

            # Python timezone
            server_time = get_utc_time()
            print(f"  Python UTC Timezone: {server_time.tzinfo}")

            # Check if system time matches Python time
            system_time = datetime.now()
            python_utc = get_utc_time()
            time_diff = abs((system_time - python_utc.replace(tzinfo=None)).total_seconds())
            
            if time_diff > 3600:  # More than 1 hour difference suggests timezone issue
                print(f"  WARNING: System time and Python UTC time differ by {time_diff/3600:.1f} hours")
            else:
                print(f"  OK: System timezone appears correct")

            self.results["timezone_info"] = {
                "system_timezone": timezone_name if 'timezone_name' in locals() else "Unknown",
                "python_utc_tz": str(server_time.tzinfo),
            }

        except Exception as e:
            print(f"  ERROR: {e}")
            self.results["timezone_info"] = {"error": str(e)}

        print()

    def generate_recommendations(self):
        """Generate recommendations based on findings"""
        print("4. RECOMMENDATIONS")
        print("-" * 80)

        recommendations = []

        # Check time drift
        time_drift = self.results.get("time_drift", {})
        avg_drift = time_drift.get("average_seconds", 0)

        if abs(avg_drift) > 3.0:
            recommendations.append({
                "priority": "High",
                "issue": "Large clock drift",
                "action": "Synchronize server clock with NTP",
                "details": f"Server clock is {abs(avg_drift):.3f}s {'ahead' if avg_drift > 0 else 'behind'} NTP. This may cause negative latency issues.",
            })
        elif abs(avg_drift) > 1.0:
            recommendations.append({
                "priority": "Medium",
                "issue": "Moderate clock drift",
                "action": "Monitor clock synchronization",
                "details": f"Server clock is {abs(avg_drift):.3f}s {'ahead' if avg_drift > 0 else 'behind'} NTP. Consider enabling NTP synchronization.",
            })

        # Check NTP connectivity
        ntp_servers = self.results.get("ntp_servers", [])
        failed_servers = [s for s in ntp_servers if s.get("status") in ["FAILED", "ERROR"]]
        if len(failed_servers) == len(ntp_servers) and len(ntp_servers) > 0:
            recommendations.append({
                "priority": "High",
                "issue": "NTP connectivity",
                "action": "Check network connectivity to NTP servers",
                "details": "Could not connect to any NTP servers. This prevents clock synchronization verification.",
            })

        if not recommendations:
            recommendations.append({
                "priority": "Info",
                "issue": "Clock synchronization",
                "action": "Continue monitoring",
                "details": "Clock appears to be well synchronized. Continue monitoring for drift.",
            })

        for rec in recommendations:
            print(f"  [{rec['priority']}] {rec['issue']}: {rec['action']}")
            print(f"      {rec['details']}")
            print()

        self.results["recommendations"] = recommendations

    def generate_report(self, output_path: str):
        """Generate markdown report"""
        import json

        report_lines = [
            "# Clock Synchronization Check Report",
            f"Generated: {datetime.now().isoformat()}",
            "",
            "## Summary",
            "",
        ]

        time_drift = self.results.get("time_drift", {})
        avg_drift = time_drift.get("average_seconds", 0)

        if abs(avg_drift) > 1.0:
            report_lines.append(f"- **Status**: WARNING - Clock drift of {abs(avg_drift):.3f}s detected")
        else:
            report_lines.append(f"- **Status**: OK - Clock is well synchronized")

        report_lines.extend([
            "",
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

    parser = argparse.ArgumentParser(description="Check clock synchronization")
    parser.add_argument("--output", type=str, default="docs/generated/CLOCK_SYNC_CHECK.md",
                        help="Output report path")

    args = parser.parse_args()

    # Run check
    checker = ClockSyncChecker()
    checker.check_all()

    # Generate report
    checker.generate_report(args.output)

    print(f"\n{'='*80}")
    print("CLOCK SYNC CHECK COMPLETE")
    print(f"{'='*80}\n")


if __name__ == "__main__":
    main()
