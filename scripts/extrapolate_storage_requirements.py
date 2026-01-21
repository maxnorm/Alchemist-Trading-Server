"""
Extrapolate storage requirements for 5 years of data across 28 currency pairs
Based on current EURUSD test data analysis
"""
from datetime import datetime, timedelta
from typing import Dict, List

# Constants from current analysis
MB_PER_DAY_PER_PAIR = 0.8642
GB_PER_DAY_PER_PAIR = 0.000844
TICKS_PER_DAY_PER_PAIR = 65429
COMPRESSION_RATIO = 2.38

# Configuration
YEARS = 5
NUMBER_OF_PAIRS = 28

def calculate_storage_requirements(years: int, pairs: int) -> Dict:
    """Calculate storage requirements for given years and pairs"""
    # Account for leap years (2020, 2024, 2028, 2032, 2036)
    # For 5 years starting from 2020-2024, we have 2 leap years
    # For 5 years starting from 2024-2028, we have 2 leap years
    # Average: ~1,826 days for 5 years (accounting for leap years)
    
    # More accurate: 5 years = 5 * 365.25 = 1,826.25 days
    days = years * 365.25
    
    # Per pair calculations
    size_mb_per_pair = MB_PER_DAY_PER_PAIR * days
    size_gb_per_pair = GB_PER_DAY_PER_PAIR * days
    ticks_per_pair = int(TICKS_PER_DAY_PER_PAIR * days)
    
    # Total for all pairs
    total_size_mb = size_mb_per_pair * pairs
    total_size_gb = size_gb_per_pair * pairs
    total_ticks = ticks_per_pair * pairs
    
    # Uncompressed sizes
    uncompressed_mb_per_pair = size_mb_per_pair * COMPRESSION_RATIO
    uncompressed_gb_per_pair = uncompressed_mb_per_pair / 1024
    total_uncompressed_mb = uncompressed_mb_per_pair * pairs
    total_uncompressed_gb = total_uncompressed_mb / 1024
    
    return {
        'years': years,
        'pairs': pairs,
        'days': days,
        'per_pair': {
            'size_mb': size_mb_per_pair,
            'size_gb': size_gb_per_pair,
            'uncompressed_mb': uncompressed_mb_per_pair,
            'uncompressed_gb': uncompressed_gb_per_pair,
            'ticks': ticks_per_pair
        },
        'total': {
            'size_mb': total_size_mb,
            'size_gb': total_size_gb,
            'uncompressed_mb': total_uncompressed_mb,
            'uncompressed_gb': total_uncompressed_gb,
            'ticks': total_ticks
        }
    }

def format_size(size_mb: float) -> str:
    """Format size in human-readable format"""
    if size_mb < 1024:
        return f"{size_mb:.2f} MB"
    elif size_mb < 1024 * 1024:
        return f"{size_mb / 1024:.2f} GB"
    else:
        return f"{size_mb / (1024 * 1024):.2f} TB"

def print_analysis(results: Dict):
    """Print detailed analysis"""
    print("=" * 80)
    print("STORAGE REQUIREMENTS EXTRAPOLATION")
    print("=" * 80)
    print()
    print(f"Configuration:")
    print(f"  Years: {results['years']}")
    print(f"  Currency Pairs: {results['pairs']}")
    print(f"  Total Days: {results['days']:.2f}")
    print()
    
    print("=" * 80)
    print("PER PAIR REQUIREMENTS")
    print("=" * 80)
    per_pair = results['per_pair']
    print(f"Compressed Size:")
    print(f"  {per_pair['size_mb']:.2f} MB ({per_pair['size_gb']:.3f} GB)")
    print(f"Uncompressed Size:")
    print(f"  {per_pair['uncompressed_mb']:.2f} MB ({per_pair['uncompressed_gb']:.3f} GB)")
    print(f"Total Ticks: {per_pair['ticks']:,}")
    print()
    
    print("=" * 80)
    print(f"TOTAL REQUIREMENTS ({results['pairs']} PAIRS)")
    print("=" * 80)
    total = results['total']
    print(f"Compressed Size:")
    print(f"  {format_size(total['size_mb'])} ({total['size_gb']:.3f} GB)")
    print(f"Uncompressed Size:")
    print(f"  {format_size(total['uncompressed_mb'])} ({total['uncompressed_gb']:.3f} GB)")
    print(f"Total Ticks: {total['ticks']:,}")
    print()
    
    # Yearly breakdown
    print("=" * 80)
    print("YEARLY BREAKDOWN (per pair)")
    print("=" * 80)
    for year in range(1, results['years'] + 1):
        year_days = 365.25 if year % 4 == 0 or (year - 1) % 4 == 0 else 365.0
        year_mb = MB_PER_DAY_PER_PAIR * year_days
        year_gb = year_mb / 1024
        year_ticks = int(TICKS_PER_DAY_PER_PAIR * year_days)
        print(f"Year {year}: {year_mb:.2f} MB ({year_gb:.3f} GB) - {year_ticks:,} ticks")
    print()
    
    # Storage scenarios
    print("=" * 80)
    print("STORAGE SCENARIOS")
    print("=" * 80)
    scenarios = [
        (1, "1 year"),
        (2, "2 years"),
        (3, "3 years"),
        (5, "5 years"),
        (10, "10 years")
    ]
    
    print(f"{'Scenario':<15} {'Per Pair':<20} {'Total ({pairs} pairs)':<25}")
    print("-" * 80)
    for years, label in scenarios:
        days = years * 365.25
        per_pair_mb = MB_PER_DAY_PER_PAIR * days
        per_pair_gb = per_pair_mb / 1024
        total_mb = per_pair_mb * NUMBER_OF_PAIRS
        total_gb = total_mb / 1024
        print(f"{label:<15} {per_pair_mb:>6.2f} MB ({per_pair_gb:>5.3f} GB)  {total_mb:>8.2f} MB ({total_gb:>6.3f} GB)")
    print()
    
    # Cost estimation (rough)
    print("=" * 80)
    print("STORAGE COST ESTIMATION (Rough)")
    print("=" * 80)
    print("Note: Costs vary significantly by provider and storage type")
    print()
    
    # Common cloud storage costs (as of 2024, approximate)
    storage_costs = {
        'AWS S3 Standard': 0.023,  # per GB/month
        'Azure Blob Hot': 0.018,   # per GB/month
        'Google Cloud Storage': 0.020,  # per GB/month
        'Local HDD': 0.0001,  # per GB (one-time, amortized)
    }
    
    total_gb = results['total']['size_gb']
    monthly_gb = total_gb  # Assuming data accumulates over time
    
    print(f"Total Storage: {total_gb:.2f} GB")
    print()
    print(f"{'Provider':<25} {'Monthly Cost':<15} {'Annual Cost':<15} {'5-Year Cost':<15}")
    print("-" * 80)
    for provider, cost_per_gb_month in storage_costs.items():
        monthly = monthly_gb * cost_per_gb_month
        annual = monthly * 12
        five_year = annual * 5
        print(f"{provider:<25} ${monthly:>6.2f}        ${annual:>6.2f}        ${five_year:>6.2f}")
    print()

def main():
    results = calculate_storage_requirements(YEARS, NUMBER_OF_PAIRS)
    print_analysis(results)
    
    # Additional insights
    print("=" * 80)
    print("ADDITIONAL INSIGHTS")
    print("=" * 80)
    print(f"Average ticks per second (per pair): {TICKS_PER_DAY_PER_PAIR / 86400:.1f}")
    print(f"Average ticks per second (all {NUMBER_OF_PAIRS} pairs): {TICKS_PER_DAY_PER_PAIR * NUMBER_OF_PAIRS / 86400:.1f}")
    print(f"Data collection rate: {MB_PER_DAY_PER_PAIR * NUMBER_OF_PAIRS:.2f} MB/day")
    print(f"Data collection rate: {MB_PER_DAY_PER_PAIR * NUMBER_OF_PAIRS / 1024:.3f} GB/day")
    print()
    print("Recommendations:")
    print("  - Use yearly partitions for optimal query performance")
    print("  - Consider compression (Snappy provides 2.38x reduction)")
    print("  - Plan for incremental growth (data accumulates over time)")
    print("  - Monitor actual vs. estimated growth")
    print("=" * 80)

if __name__ == '__main__':
    main()
