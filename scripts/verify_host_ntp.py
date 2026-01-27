#!/usr/bin/env python
"""
Host NTP Synchronization Verification Script

This script verifies that the host system (Linux/Windows) has NTP synchronization
properly configured and running. This is critical because Docker containers inherit
the host kernel clock via VDSO, so the host must be NTP-synchronized.

Verifies:
1. NTP service status (Linux: systemd-timesyncd/chronyd, Windows: w32tm)
2. NTP server connectivity
3. Current clock drift
4. Docker container time inheritance
5. Provides remediation steps
"""

import os
import sys
import subprocess
import platform
import socket
import struct
from datetime import datetime, timezone
from typing import Dict, List, Optional, Tuple
from pathlib import Path


class HostNTPVerifier:
    """Verify host system NTP synchronization"""

    # NTP protocol constants
    NTP_PACKET_FORMAT = "!12I"
    NTP_DELTA = 2208988800  # 1970-01-01 00:00:00

    def __init__(self):
        self.system = platform.system().lower()
        self.results = {
            "system": self.system,
            "ntp_service_status": None,
            "ntp_servers": [],
            "clock_drift": None,
            "docker_time_check": None,
            "remediation_steps": [],
            "overall_status": "unknown",
        }

    def verify_all(self) -> Dict:
        """Run all verification checks"""
        print(f"\n{'='*80}")
        print("HOST NTP SYNCHRONIZATION VERIFICATION")
        print(f"{'='*80}\n")

        # 1. Check NTP service status
        self.check_ntp_service_status()

        # 2. Verify NTP server connectivity
        self.check_ntp_server_connectivity()

        # 3. Check clock drift
        self.check_clock_drift()

        # 4. Verify Docker container time inheritance (if Docker available)
        self.check_docker_time_inheritance()

        # 5. Generate remediation steps
        self.generate_remediation_steps()

        # 6. Determine overall status
        self.determine_overall_status()

        return self.results

    def check_ntp_service_status(self):
        """Check if NTP service is running on the host"""
        print("1. NTP SERVICE STATUS CHECK")
        print("-" * 80)

        if self.system == "linux":
            self._check_linux_ntp_service()
        elif self.system == "windows":
            self._check_windows_ntp_service()
        else:
            print(f"  WARNING: Unsupported system '{self.system}'")
            self.results["ntp_service_status"] = {
                "status": "unknown",
                "error": f"Unsupported system: {self.system}",
            }

        print()

    def _check_linux_ntp_service(self):
        """Check Linux NTP service (systemd-timesyncd or chronyd)"""
        service_status = {
            "service": None,
            "status": "unknown",
            "active": False,
            "enabled": False,
            "details": {},
        }

        # Check systemd-timesyncd (most common on modern Linux)
        try:
            result = subprocess.run(
                ["systemctl", "is-active", "systemd-timesyncd"],
                capture_output=True,
                text=True,
                timeout=5,
            )
            if result.returncode == 0 and result.stdout.strip() == "active":
                service_status["service"] = "systemd-timesyncd"
                service_status["active"] = True

                # Check if enabled
                result = subprocess.run(
                    ["systemctl", "is-enabled", "systemd-timesyncd"],
                    capture_output=True,
                    text=True,
                    timeout=5,
                )
                service_status["enabled"] = (
                    result.returncode == 0 and "enabled" in result.stdout
                )

                # Get detailed status
                result = subprocess.run(
                    ["timedatectl", "status"],
                    capture_output=True,
                    text=True,
                    timeout=5,
                )
                if result.returncode == 0:
                    service_status["details"]["timedatectl_output"] = result.stdout

                # Check synchronization status
                if "synchronized: yes" in result.stdout.lower():
                    service_status["status"] = "synchronized"
                elif "synchronized: no" in result.stdout.lower():
                    service_status["status"] = "not_synchronized"
                else:
                    service_status["status"] = "active"

                print(f"  [✓] NTP Service: systemd-timesyncd")
                print(f"      Status: {service_status['status']}")
                print(f"      Active: {'Yes' if service_status['active'] else 'No'}")
                print(f"      Enabled: {'Yes' if service_status['enabled'] else 'No'}")

        except (subprocess.TimeoutExpired, FileNotFoundError, subprocess.SubprocessError):
            pass

        # Check chronyd as fallback
        if not service_status["active"]:
            try:
                result = subprocess.run(
                    ["systemctl", "is-active", "chronyd"],
                    capture_output=True,
                    text=True,
                    timeout=5,
                )
                if result.returncode == 0 and result.stdout.strip() == "active":
                    service_status["service"] = "chronyd"
                    service_status["active"] = True

                    # Check if enabled
                    result = subprocess.run(
                        ["systemctl", "is-enabled", "chronyd"],
                        capture_output=True,
                        text=True,
                        timeout=5,
                    )
                    service_status["enabled"] = (
                        result.returncode == 0 and "enabled" in result.stdout
                    )

                    # Get sources
                    result = subprocess.run(
                        ["chronyc", "sources"],
                        capture_output=True,
                        text=True,
                        timeout=5,
                    )
                    if result.returncode == 0:
                        service_status["details"]["chronyc_sources"] = result.stdout

                    print(f"  [✓] NTP Service: chronyd")
                    print(f"      Status: Active")
                    print(f"      Enabled: {'Yes' if service_status['enabled'] else 'No'}")

            except (subprocess.TimeoutExpired, FileNotFoundError, subprocess.SubprocessError):
                pass

        # Check ntpd as last resort
        if not service_status["active"]:
            try:
                result = subprocess.run(
                    ["systemctl", "is-active", "ntpd"],
                    capture_output=True,
                    text=True,
                    timeout=5,
                )
                if result.returncode == 0 and result.stdout.strip() == "active":
                    service_status["service"] = "ntpd"
                    service_status["active"] = True
                    print(f"  [✓] NTP Service: ntpd")
                    print(f"      Status: Active")
            except (subprocess.TimeoutExpired, FileNotFoundError, subprocess.SubprocessError):
                pass

        if not service_status["active"]:
            print(f"  [✗] NTP Service: NOT RUNNING")
            print(f"      No active NTP service detected (checked: systemd-timesyncd, chronyd, ntpd)")
            service_status["status"] = "not_running"

        self.results["ntp_service_status"] = service_status

    def _check_windows_ntp_service(self):
        """Check Windows Time service (w32tm)"""
        service_status = {
            "service": "w32tm",
            "status": "unknown",
            "active": False,
            "enabled": False,
            "details": {},
        }

        try:
            # Check Windows Time service status
            result = subprocess.run(
                ["w32tm", "/query", "/status"],
                capture_output=True,
                text=True,
                timeout=10,
            )

            if result.returncode == 0:
                output = result.stdout
                service_status["details"]["w32tm_status"] = output

                # Check if synchronized
                if "Source:" in output:
                    service_status["active"] = True
                    if "Local CMOS Clock" in output:
                        service_status["status"] = "not_synchronized"
                        print(f"  [✗] NTP Service: Windows Time Service")
                        print(f"      Status: Using Local CMOS Clock (NOT synchronized)")
                    elif any(
                        server in output
                        for server in ["time.windows.com", "pool.ntp.org", "time.nist.gov"]
                    ):
                        service_status["status"] = "synchronized"
                        print(f"  [✓] NTP Service: Windows Time Service")
                        print(f"      Status: Synchronized")
                    else:
                        service_status["status"] = "active"
                        print(f"  [✓] NTP Service: Windows Time Service")
                        print(f"      Status: Active")

                # Check configuration
                result = subprocess.run(
                    ["w32tm", "/query", "/configuration"],
                    capture_output=True,
                    text=True,
                    timeout=10,
                )
                if result.returncode == 0:
                    service_status["details"]["w32tm_config"] = result.stdout
                    if "Type: NTP" in result.stdout:
                        service_status["enabled"] = True

            else:
                print(f"  [✗] NTP Service: Windows Time Service")
                print(f"      Status: Could not query service")
                service_status["status"] = "error"
                service_status["details"]["error"] = result.stderr

        except (subprocess.TimeoutExpired, FileNotFoundError, subprocess.SubprocessError) as e:
            print(f"  [✗] NTP Service: Windows Time Service")
            print(f"      Status: Error checking service - {e}")
            service_status["status"] = "error"
            service_status["details"]["error"] = str(e)

        self.results["ntp_service_status"] = service_status

    def check_ntp_server_connectivity(self):
        """Verify connectivity to NTP servers"""
        print("2. NTP SERVER CONNECTIVITY CHECK")
        print("-" * 80)

        ntp_servers = [
            "pool.ntp.org",
            "time.google.com",
            "time.cloudflare.com",
            "time.windows.com",
        ]

        server_time = datetime.now(timezone.utc)
        successful_checks = 0
        total_drift = 0.0

        print(f"  Testing connectivity to NTP servers...")
        print(f"  {'Server':<25} {'Status':<15} {'Drift (s)':<15}")
        print("-" * 55)

        for server in ntp_servers:
            ntp_time = self._get_ntp_time(server)
            if ntp_time:
                drift_seconds = (server_time - ntp_time).total_seconds()
                total_drift += drift_seconds
                successful_checks += 1

                status = "OK" if abs(drift_seconds) < 1.0 else "WARNING"
                print(f"  {server:<25} {status:<15} {drift_seconds:>10.3f}")

                self.results["ntp_servers"].append(
                    {
                        "server": server,
                        "status": "reachable",
                        "drift_seconds": drift_seconds,
                    }
                )
            else:
                print(f"  {server:<25} {'UNREACHABLE':<15} {'N/A':<15}")
                self.results["ntp_servers"].append(
                    {"server": server, "status": "unreachable"}
                )

        if successful_checks > 0:
            avg_drift = total_drift / successful_checks
            self.results["clock_drift"] = {
                "average_seconds": avg_drift,
                "successful_checks": successful_checks,
            }
            print(f"\n  Average Drift: {avg_drift:.3f} seconds")
            if abs(avg_drift) > 1.0:
                print(
                    f"  WARNING: Clock drift exceeds threshold (1.0s) - {abs(avg_drift):.3f}s"
                )
            else:
                print(f"  OK: Clock drift within acceptable range")
        else:
            print(f"\n  ERROR: Could not reach any NTP servers")
            self.results["clock_drift"] = {"error": "No successful NTP checks"}

        print()

    def _get_ntp_time(self, host: str, port: int = 123, timeout: int = 5) -> Optional[datetime]:
        """Get time from NTP server"""
        try:
            client = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
            client.settimeout(timeout)

            # Send NTP request
            data = b"\x1b" + 47 * b"\0"
            client.sendto(data, (host, port))

            # Receive response
            data, address = client.recvfrom(1024)
            client.close()

            # Parse NTP response
            if data:
                unpacked = struct.unpack(
                    self.NTP_PACKET_FORMAT,
                    data[0 : struct.calcsize(self.NTP_PACKET_FORMAT)],
                )
                seconds = unpacked[10] - self.NTP_DELTA
                fraction = unpacked[11] / 2**32
                ntp_time = seconds + fraction
                return datetime.fromtimestamp(ntp_time, tz=timezone.utc)
        except Exception:
            return None
        return None

    def check_clock_drift(self):
        """Check current clock drift"""
        print("3. CLOCK DRIFT CHECK")
        print("-" * 80)

        drift_info = self.results.get("clock_drift", {})
        if "average_seconds" in drift_info:
            avg_drift = drift_info["average_seconds"]
            print(f"  Current Drift: {avg_drift:.3f} seconds")

            if abs(avg_drift) <= 0.1:
                print(f"  Status: EXCELLENT - Well synchronized")
            elif abs(avg_drift) <= 1.0:
                print(f"  Status: ACCEPTABLE - Within threshold")
            elif abs(avg_drift) <= 5.0:
                print(f"  Status: WARNING - Exceeds threshold")
            else:
                print(f"  Status: CRITICAL - Large drift detected")
        else:
            print(f"  Status: UNABLE TO DETERMINE - No NTP connectivity")

        print()

    def check_docker_time_inheritance(self):
        """Verify Docker container inherits host time"""
        print("4. DOCKER CONTAINER TIME CHECK")
        print("-" * 80)

        docker_check = {"available": False, "host_time": None, "container_time": None, "match": False}

        # Check if Docker is available
        try:
            result = subprocess.run(
                ["docker", "--version"],
                capture_output=True,
                text=True,
                timeout=5,
            )
            if result.returncode == 0:
                docker_check["available"] = True
                print(f"  Docker: Available")

                # Get host time
                host_time = datetime.now(timezone.utc)
                docker_check["host_time"] = host_time.isoformat()

                # Try to get container time (if trading_server container exists)
                try:
                    result = subprocess.run(
                        ["docker", "exec", "server", "date", "-u", "+%Y-%m-%dT%H:%M:%S"],
                        capture_output=True,
                        text=True,
                        timeout=5,
                    )
                    if result.returncode == 0:
                        container_time_str = result.stdout.strip()
                        container_time = datetime.fromisoformat(container_time_str).replace(
                            tzinfo=timezone.utc
                        )
                        docker_check["container_time"] = container_time.isoformat()

                        # Compare times (allow 1 second difference for processing delay)
                        time_diff = abs((host_time - container_time).total_seconds())
                        docker_check["match"] = time_diff < 1.0
                        docker_check["time_diff_seconds"] = time_diff

                        if docker_check["match"]:
                            print(f"  [✓] Host-Container Time Match: YES")
                            print(f"      Host:   {host_time.isoformat()[:19]}")
                            print(f"      Container: {container_time.isoformat()[:19]}")
                        else:
                            print(f"  [✗] Host-Container Time Match: NO")
                            print(f"      Host:   {host_time.isoformat()[:19]}")
                            print(f"      Container: {container_time.isoformat()[:19]}")
                            print(f"      Difference: {time_diff:.3f}s")
                    else:
                        print(f"  [⚠] Could not query container time (container may not be running)")
                except (subprocess.TimeoutExpired, subprocess.SubprocessError):
                    print(f"  [⚠] Could not query container time (container may not be running)")
            else:
                print(f"  Docker: Not available (skipping container check)")
        except (FileNotFoundError, subprocess.TimeoutExpired, subprocess.SubprocessError):
            print(f"  Docker: Not available (skipping container check)")

        self.results["docker_time_check"] = docker_check
        print()

    def generate_remediation_steps(self):
        """Generate remediation steps based on findings"""
        print("5. REMEDIATION STEPS")
        print("-" * 80)

        steps = []

        # Check NTP service status
        ntp_status = self.results.get("ntp_service_status", {})
        if ntp_status.get("status") == "not_running":
            if self.system == "linux":
                steps.append(
                    {
                        "priority": "HIGH",
                        "action": "Enable NTP synchronization",
                        "command": "sudo timedatectl set-ntp true",
                        "description": "Enable systemd-timesyncd to synchronize with NTP servers",
                    }
                )
            elif self.system == "windows":
                steps.append(
                    {
                        "priority": "HIGH",
                        "action": "Enable Windows Time service",
                        "command": "w32tm /config /manualpeerlist:time.windows.com /syncfromflags:manual /reliable:yes /update",
                        "description": "Configure Windows Time service to use NTP",
                    }
                )
                steps.append(
                    {
                        "priority": "HIGH",
                        "action": "Start Windows Time service",
                        "command": "net start w32time",
                        "description": "Start the Windows Time service",
                    }
                )

        elif ntp_status.get("status") == "not_synchronized":
            if self.system == "linux":
                steps.append(
                    {
                        "priority": "MEDIUM",
                        "action": "Force NTP synchronization",
                        "command": "sudo systemctl restart systemd-timesyncd",
                        "description": "Restart NTP service to force synchronization",
                    }
                )
            elif self.system == "windows":
                steps.append(
                    {
                        "priority": "MEDIUM",
                        "action": "Resync Windows Time",
                        "command": "w32tm /resync",
                        "description": "Force Windows Time service to resynchronize",
                    }
                )

        # Check clock drift
        drift_info = self.results.get("clock_drift", {})
        if "average_seconds" in drift_info:
            avg_drift = abs(drift_info["average_seconds"])
            if avg_drift > 1.0:
                steps.append(
                    {
                        "priority": "HIGH",
                        "action": "Fix clock drift",
                        "command": "See NTP service steps above",
                        "description": f"Clock drift of {avg_drift:.3f}s exceeds threshold. Enable/restart NTP service.",
                    }
                )

        # Check NTP connectivity
        ntp_servers = self.results.get("ntp_servers", [])
        unreachable = [s for s in ntp_servers if s.get("status") == "unreachable"]
        if len(unreachable) == len(ntp_servers) and len(ntp_servers) > 0:
            steps.append(
                {
                    "priority": "HIGH",
                    "action": "Check firewall rules",
                    "command": "sudo ufw allow 123/udp  # Linux",
                    "description": "Ensure UDP port 123 is open for NTP traffic",
                }
            )
            steps.append(
                {
                    "priority": "MEDIUM",
                    "action": "Check network connectivity",
                    "command": "ping pool.ntp.org",
                    "description": "Verify network connectivity to NTP servers",
                }
            )

        # Docker container restart
        docker_check = self.results.get("docker_time_check", {})
        if docker_check.get("available") and not docker_check.get("match"):
            steps.append(
                {
                    "priority": "MEDIUM",
                    "action": "Restart Docker containers",
                    "command": "docker compose restart server",
                    "description": "Restart containers to pick up corrected host time",
                }
            )

        if not steps:
            steps.append(
                {
                    "priority": "INFO",
                    "action": "No action needed",
                    "command": "N/A",
                    "description": "Host NTP synchronization appears to be working correctly",
                }
            )

        for step in steps:
            print(f"  [{step['priority']}] {step['action']}")
            print(f"      Command: {step['command']}")
            print(f"      {step['description']}")
            print()

        self.results["remediation_steps"] = steps

    def determine_overall_status(self):
        """Determine overall verification status"""
        print("6. OVERALL STATUS")
        print("-" * 80)

        status = "PASS"
        issues = []

        # Check NTP service
        ntp_status = self.results.get("ntp_service_status", {})
        if ntp_status.get("status") in ["not_running", "not_synchronized"]:
            status = "FAIL"
            issues.append("NTP service not running or not synchronized")

        # Check clock drift
        drift_info = self.results.get("clock_drift", {})
        if "average_seconds" in drift_info:
            avg_drift = abs(drift_info["average_seconds"])
            if avg_drift > 1.0:
                status = "FAIL"
                issues.append(f"Clock drift exceeds threshold ({avg_drift:.3f}s)")
            elif avg_drift > 0.5:
                status = "WARNING"
                issues.append(f"Clock drift approaching threshold ({avg_drift:.3f}s)")

        # Check NTP connectivity
        ntp_servers = self.results.get("ntp_servers", [])
        unreachable = [s for s in ntp_servers if s.get("status") == "unreachable"]
        if len(unreachable) == len(ntp_servers) and len(ntp_servers) > 0:
            status = "FAIL"
            issues.append("Cannot reach any NTP servers")

        if status == "PASS":
            print(f"  [✓] Result: PASS - System ready for deployment")
        elif status == "WARNING":
            print(f"  [⚠] Result: WARNING - {', '.join(issues)}")
        else:
            print(f"  [✗] Result: FAIL - {', '.join(issues)}")
            print(f"\n  Fix the issues above before deploying the trading server.")

        self.results["overall_status"] = status
        self.results["issues"] = issues
        print()

    def generate_report(self, output_path: str):
        """Generate markdown report"""
        import json

        report_lines = [
            "# Host NTP Synchronization Verification Report",
            f"Generated: {datetime.now(timezone.utc).isoformat()}",
            f"System: {self.system}",
            "",
            "## Summary",
            "",
            f"- **Overall Status**: {self.results['overall_status']}",
        ]

        if self.results.get("issues"):
            report_lines.append("- **Issues**:")
            for issue in self.results["issues"]:
                report_lines.append(f"  - {issue}")

        report_lines.extend(
            [
                "",
                "## Detailed Results",
                "",
                "```json",
                json.dumps(self.results, indent=2, default=str),
                "```",
            ]
        )

        output_file = Path(output_path)
        output_file.parent.mkdir(parents=True, exist_ok=True)
        output_file.write_text("\n".join(report_lines), encoding="utf-8")
        print(f"Report saved to: {output_path}")


def main():
    """Main entry point"""
    import argparse

    parser = argparse.ArgumentParser(
        description="Verify host system NTP synchronization"
    )
    parser.add_argument(
        "--output",
        type=str,
        default="docs/generated/HOST_NTP_VERIFICATION.md",
        help="Output report path",
    )

    args = parser.parse_args()

    # Run verification
    verifier = HostNTPVerifier()
    verifier.verify_all()

    # Generate report
    verifier.generate_report(args.output)

    print(f"\n{'='*80}")
    print("HOST NTP VERIFICATION COMPLETE")
    print(f"{'='*80}\n")

    # Exit with appropriate code
    if verifier.results["overall_status"] == "FAIL":
        sys.exit(1)
    elif verifier.results["overall_status"] == "WARNING":
        sys.exit(2)
    else:
        sys.exit(0)


if __name__ == "__main__":
    main()
