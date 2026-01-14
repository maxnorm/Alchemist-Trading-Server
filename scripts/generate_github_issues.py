#!/usr/bin/env python3
"""
Parse the consolidated Beta-MVP backlog and generate individual GitHub issue files.

Each issue is extracted from the backlog and saved as a separate markdown file.
Can optionally create issues directly on GitHub using GitHub CLI.

Usage:
    python scripts/generate_github_issues.py                    # Generate files only
    python scripts/generate_github_issues.py --create            # Generate files and create issues
    python scripts/generate_github_issues.py --create --dry-run  # Dry run (no actual creation)
"""

import re
import os
import subprocess
import sys
import argparse
from pathlib import Path
from typing import Dict, List, Optional, Tuple


def parse_issue_section(content: str, start_idx: int) -> Optional[Dict[str, any]]:
    """Parse a single issue from the backlog starting at start_idx."""
    
    # Find the issue header
    issue_header_pattern = r'##### \*\*Issue #(\d+): (.+?)\*\*'
    header_match = re.search(issue_header_pattern, content[start_idx:])
    if not header_match:
        return None
    
    issue_num = int(header_match.group(1))
    issue_title_short = header_match.group(2)
    issue_start = start_idx + header_match.end()
    
    # Find the next issue or end of section
    next_issue_pattern = r'##### \*\*Issue #'
    next_match = re.search(next_issue_pattern, content[issue_start:])
    if next_match:
        issue_end = issue_start + next_match.start()
    else:
        # Find next epic or end of document
        next_epic_pattern = r'#### \*\*EPIC \d+:'
        epic_match = re.search(next_epic_pattern, content[issue_start:])
        if epic_match:
            issue_end = issue_start + epic_match.start()
        else:
            issue_end = len(content)
    
    issue_content = content[issue_start:issue_end].strip()
    
    # Extract fields
    issue_data = {
        'number': issue_num,
        'title_short': issue_title_short,
        'raw_content': issue_content
    }
    
    # Extract Title
    title_match = re.search(r'\*\*Title:\*\* (.+?)(?:\n|$)', issue_content, re.MULTILINE)
    if title_match:
        issue_data['title'] = title_match.group(1).strip()
    else:
        issue_data['title'] = issue_title_short
    
    # Extract Labels
    labels_match = re.search(r'\*\*Labels:\*\* (.+?)(?:\n|$)', issue_content, re.MULTILINE)
    if labels_match:
        # Extract all labels (format: `label1`, `label2`, `label3`)
        labels_str = labels_match.group(1).strip()
        # Find all labels wrapped in backticks
        label_pattern = r'`([^`]+)`'
        issue_data['labels'] = re.findall(label_pattern, labels_str)
    else:
        issue_data['labels'] = []
    
    # Extract Milestone
    milestone_match = re.search(r'\*\*Milestone:\*\* (.+?)(?:\n|$)', issue_content, re.MULTILINE)
    if milestone_match:
        issue_data['milestone'] = milestone_match.group(1).strip()
    else:
        issue_data['milestone'] = ''
    
    # Extract sections
    sections = {
        'Problem Statement': extract_section(issue_content, 'Problem Statement'),
        'Evidence': extract_section(issue_content, 'Evidence'),
        'Proposed Solution': extract_section(issue_content, 'Proposed Solution'),
        'Acceptance Criteria': extract_section(issue_content, 'Acceptance Criteria'),
        'How to Verify': extract_section(issue_content, 'How to Verify'),
        'Risk': extract_section(issue_content, 'Risk'),
        'Effort': extract_field(issue_content, 'Effort'),
        'Dependencies': extract_field(issue_content, 'Dependencies'),
        'Owner Role': extract_field(issue_content, 'Owner Role'),
    }
    
    issue_data.update(sections)
    
    return issue_data, issue_end


def extract_section(content: str, section_name: str) -> str:
    """Extract a section from the issue content."""
    # Pattern to match section header and content until next section or end
    # Look for the section header, then capture everything until the next ** section or end
    pattern = rf'\*\*{re.escape(section_name)}:\*\*\s*\n\n(.*?)(?=\n\n\*\*[A-Z]|\n\n---|\Z)'
    match = re.search(pattern, content, re.DOTALL)
    if match:
        text = match.group(1).strip()
        # Remove trailing newlines that might be part of the next section
        return text
    return ''


def extract_field(content: str, field_name: str) -> str:
    """Extract a single-line field from the issue content."""
    pattern = rf'\*\*{re.escape(field_name)}:\*\* (.+?)(?:\n|$)'
    match = re.search(pattern, content, re.MULTILINE)
    if match:
        return match.group(1).strip()
    return ''


def format_github_issue_body(issue: Dict[str, any]) -> str:
    """Format an issue body for GitHub (used for CLI creation)."""
    
    lines = [
        f"## Issue #{issue['number']}: {issue['title']}",
        '',
    ]
    
    # Add sections
    if issue.get('Problem Statement'):
        lines.extend([
            '## Problem Statement',
            '',
            issue['Problem Statement'],
            '',
        ])
    
    if issue.get('Evidence'):
        lines.extend([
            '## Evidence',
            '',
            issue['Evidence'],
            '',
        ])
    
    if issue.get('Proposed Solution'):
        lines.extend([
            '## Proposed Solution',
            '',
            issue['Proposed Solution'],
            '',
        ])
    
    if issue.get('Acceptance Criteria'):
        lines.extend([
            '## Acceptance Criteria',
            '',
            issue['Acceptance Criteria'],
            '',
        ])
    
    if issue.get('How to Verify'):
        lines.extend([
            '## How to Verify',
            '',
            '```bash',
            issue['How to Verify'],
            '```',
            '',
        ])
    
    if issue.get('Risk'):
        lines.extend([
            '## Risk',
            '',
            issue['Risk'],
            '',
        ])
    
    # Add metadata
    metadata = []
    if issue.get('Effort'):
        metadata.append(f"- **Effort:** {issue['Effort']}")
    if issue.get('Dependencies'):
        metadata.append(f"- **Dependencies:** {issue['Dependencies']}")
    if issue.get('Owner Role'):
        metadata.append(f"- **Owner Role:** {issue['Owner Role']}")
    
    if metadata:
        lines.extend([
            '## Metadata',
            '',
            *metadata,
            '',
        ])
    
    return '\n'.join(lines)


def format_github_issue_file(issue: Dict[str, any]) -> str:
    """Format an issue as a GitHub issue markdown file (for VSCode extension)."""
    
    lines = [
        issue['title'],
        '',
        '<!-- This issue will be created in repo maxnorm/Alchemist-AI (https://github.com/maxnorm/Alchemist-AI). Changing this line has no effect. -->',
        '',
        'Assignees: ',
        f"Labels: {', '.join(issue['labels'])}" if issue['labels'] else 'Labels: ',
        f"Milestone: {issue['milestone']}" if issue['milestone'] else 'Milestone: ',
        'Projects: ',
        '',
        '',
        '<!-- Edit the body of your new issue then click the ✓ "Create Issue" button in the top right of the editor. The first line will be the issue title. Assignees and Labels follow after a blank line. Leave an empty line before beginning the body of the issue. -->',
        '',
        '---',
        '',
    ]
    
    # Add the body content
    body = format_github_issue_body(issue)
    lines.append(body)
    
    return '\n'.join(lines)


def parse_all_issues(backlog_path: Path) -> List[Dict[str, any]]:
    """Parse all issues from the backlog file."""
    
    with open(backlog_path, 'r', encoding='utf-8') as f:
        content = f.read()
    
    # Find the start of issue templates section
    issue_section_pattern = r'### 5\.2 Issue Templates'
    section_match = re.search(issue_section_pattern, content)
    if not section_match:
        raise ValueError("Could not find 'Issue Templates' section in backlog")
    
    start_idx = section_match.end()
    issues = []
    
    while True:
        result = parse_issue_section(content, start_idx)
        if result is None:
            break
        
        issue_data, next_idx = result
        issues.append(issue_data)
        start_idx = next_idx
    
    return issues


def check_gh_cli() -> bool:
    """Check if GitHub CLI is installed and authenticated."""
    try:
        result = subprocess.run(['gh', '--version'], capture_output=True, text=True)
        if result.returncode != 0:
            return False
        
        # Check if authenticated
        auth_result = subprocess.run(['gh', 'auth', 'status'], capture_output=True, text=True)
        return auth_result.returncode == 0
    except FileNotFoundError:
        return False


def create_github_issue(issue: Dict[str, any], dry_run: bool = False) -> Tuple[bool, str]:
    """Create a GitHub issue using GitHub CLI."""
    
    title = issue['title']
    body = format_github_issue_body(issue)
    
    # Build gh command
    cmd = ['gh', 'issue', 'create', '--title', title, '--body', body]
    
    # Add labels
    if issue.get('labels'):
        for label in issue['labels']:
            cmd.extend(['--label', label])
    
    # Add milestone (if exists and not empty)
    if issue.get('milestone'):
        cmd.extend(['--milestone', issue['milestone']])
    
    if dry_run:
        print(f"[DRY RUN] Would run: {' '.join(cmd)}")
        return True, "Dry run - no issue created"
    
    try:
        result = subprocess.run(cmd, capture_output=True, text=True, check=True)
        issue_url = result.stdout.strip()
        return True, issue_url
    except subprocess.CalledProcessError as e:
        return False, f"Error: {e.stderr}"


def main():
    """Main function to generate issue files and optionally create issues."""
    
    parser = argparse.ArgumentParser(
        description='Parse backlog and generate GitHub issue files',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Generate issue files only
  python scripts/generate_github_issues.py
  
  # Generate files and create issues on GitHub
  python scripts/generate_github_issues.py --create
  
  # Dry run (show what would be created)
  python scripts/generate_github_issues.py --create --dry-run
        """
    )
    parser.add_argument(
        '--create',
        action='store_true',
        help='Create issues on GitHub using GitHub CLI (requires gh CLI and authentication)'
    )
    parser.add_argument(
        '--dry-run',
        action='store_true',
        help='Show what would be created without actually creating issues'
    )
    parser.add_argument(
        '--output-dir',
        type=str,
        default=None,
        help='Directory to save issue files (default: .github/ISSUES for VSCode extension)'
    )
    
    args = parser.parse_args()
    
    # Paths
    repo_root = Path(__file__).parent.parent
    backlog_path = repo_root / 'docs' / 'generated' / 'beta_mvp_backlog_consolidated.md'
    
    # Determine output directory
    if args.output_dir:
        issues_dir = Path(args.output_dir)
    else:
        # Use .github/ISSUES for VSCode extension compatibility
        issues_dir = repo_root / '.github' / 'ISSUES'
    
    # Create issues directory
    issues_dir.mkdir(parents=True, exist_ok=True)
    
    # Check GitHub CLI if creating issues
    if args.create and not args.dry_run:
        if not check_gh_cli():
            print("ERROR: GitHub CLI (gh) is not installed or not authenticated.")
            print("Please install GitHub CLI: https://cli.github.com/")
            print("Then authenticate: gh auth login")
            sys.exit(1)
    
    # Parse issues
    print(f"Parsing backlog from: {backlog_path}")
    if not backlog_path.exists():
        print(f"ERROR: Backlog file not found: {backlog_path}")
        sys.exit(1)
    
    issues = parse_all_issues(backlog_path)
    print(f"Found {len(issues)} issues")
    
    # Generate issue files
    created_count = 0
    failed_count = 0
    
    for issue in issues:
        issue_num = issue['number']
        # Sanitize filename
        title_slug = re.sub(r'[^\w\s-]', '', issue['title_short']).strip()
        title_slug = re.sub(r'[-\s]+', '_', title_slug)
        filename = f"issue_{issue_num:02d}_{title_slug}.md"
        filepath = issues_dir / filename
        
        # Generate file content (for VSCode extension)
        issue_content = format_github_issue_file(issue)
        
        with open(filepath, 'w', encoding='utf-8') as f:
            f.write(issue_content)
        
        print(f"Generated: {filepath}")
        
        # Create issue on GitHub if requested
        if args.create:
            success, message = create_github_issue(issue, dry_run=args.dry_run)
            if success:
                created_count += 1
                if not args.dry_run:
                    print(f"  ✓ Created issue: {message}")
                else:
                    print(f"  [DRY RUN] Would create issue: {issue['title']}")
            else:
                failed_count += 1
                print(f"  ✗ Failed to create issue: {message}")
    
    # Summary
    print(f"\n{'='*60}")
    print(f"Summary:")
    print(f"  Generated {len(issues)} issue files in {issues_dir}")
    if args.create:
        if args.dry_run:
            print(f"  [DRY RUN] Would create {len(issues)} issues")
        else:
            print(f"  Created {created_count} issues on GitHub")
            if failed_count > 0:
                print(f"  Failed to create {failed_count} issues")
    
    print(f"\nIssue files location: {issues_dir}")
    print("\nNext steps:")
    if not args.create:
        print("1. Review the generated issue files")
        print("2. Create issues manually via GitHub VSCode extension:")
        print(f"   - Open files in {issues_dir}")
        print("   - Use GitHub extension to create issues from these files")
        print("3. Or use GitHub CLI:")
        print("   python scripts/generate_github_issues.py --create")
    else:
        if args.dry_run:
            print("1. Review the output above")
            print("2. Run without --dry-run to create issues:")
            print("   python scripts/generate_github_issues.py --create")
        else:
            print("1. Issues have been created on GitHub")
            print("2. Review issues at: https://github.com/maxnorm/Alchemist-AI/issues")


if __name__ == '__main__':
    main()
