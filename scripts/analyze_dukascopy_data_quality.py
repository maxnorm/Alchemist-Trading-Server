#!/usr/bin/env python3
"""
Comprehensive Dukascopy Data Quality Analysis Script

Analyzes parquet files to assess data quality with detailed statistics,
visualizations, and quality scores.
"""

import argparse
import json
import logging
from pathlib import Path
from datetime import datetime, timedelta
from typing import Dict, List, Optional
import pandas as pd
import numpy as np
import matplotlib
matplotlib.use('Agg')  # Non-interactive backend
import matplotlib.pyplot as plt
import seaborn as sns
import pyarrow.parquet as pq
import warnings
warnings.filterwarnings('ignore')

# Setup logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger('data_quality_analysis')

# Set style
plt.style.use('seaborn-v0_8-darkgrid')
sns.set_palette("husl")


class DataQualityAnalyzer:
    """Comprehensive data quality analyzer for Dukascopy parquet files"""
    
    def __init__(self, parquet_file: Path, symbol: str, output_dir: Optional[Path] = None):
        self.parquet_file = parquet_file
        self.symbol = symbol
        self.output_dir = output_dir or parquet_file.parent
        self.df = None
        self.results = {}
        
    def load_data(self) -> pd.DataFrame:
        """Load and prepare parquet file"""
        logger.info(f"Loading data from: {self.parquet_file}")
        
        if not self.parquet_file.exists():
            raise FileNotFoundError(f"Parquet file not found: {self.parquet_file}")
        
        self.df = pd.read_parquet(self.parquet_file)
        
        # Ensure timestamp is datetime
        if not pd.api.types.is_datetime64_any_dtype(self.df['timestamp']):
            self.df['timestamp'] = pd.to_datetime(self.df['timestamp'], utc=True)
        
        # Sort by timestamp
        self.df = self.df.sort_values('timestamp').reset_index(drop=True)
        
        logger.info(f"Loaded {len(self.df):,} records")
        logger.info(f"Date range: {self.df['timestamp'].min()} to {self.df['timestamp'].max()}")
        
        return self.df
    
    def analyze_basic_info(self) -> Dict:
        """Analyze basic file information"""
        logger.info("Analyzing basic information...")
        
        # Read metadata
        parquet_file_obj = pq.ParquetFile(self.parquet_file)
        metadata = parquet_file_obj.schema_arrow.metadata
        
        file_size_mb = self.parquet_file.stat().st_size / (1024 * 1024)
        
        result = {
            'file_path': str(self.parquet_file),
            'symbol': self.symbol,
            'total_records': len(self.df),
            'file_size_mb': round(file_size_mb, 2),
            'date_range': {
                'start': self.df['timestamp'].min().isoformat(),
                'end': self.df['timestamp'].max().isoformat()
            },
            'duration_days': (self.df['timestamp'].max() - self.df['timestamp'].min()).days,
            'columns': list(self.df.columns),
            'dtypes': {str(k): str(v) for k, v in self.df.dtypes.items()}
        }
        
        # Extract metadata if available
        if metadata:
            metadata_dict = {}
            for key, value in metadata.items():
                try:
                    metadata_dict[key.decode()] = value.decode()
                except:
                    metadata_dict[key.decode()] = str(value)
            result['parquet_metadata'] = metadata_dict
        
        self.results['basic_info'] = result
        return result
    
    def analyze_completeness(self) -> Dict:
        """Analyze data completeness"""
        logger.info("Analyzing data completeness...")
        
        # Null values
        null_counts = self.df.isnull().sum().to_dict()
        total_nulls = sum(null_counts.values())
        
        # Duplicates
        duplicate_count = self.df.duplicated().sum()
        
        # Date coverage
        date_range = pd.date_range(
            start=self.df['timestamp'].min().date(),
            end=self.df['timestamp'].max().date(),
            freq='D'
        )
        actual_dates = set(self.df['timestamp'].dt.date.unique())
        expected_dates = set(date_range.date)
        missing_dates = sorted(expected_dates - actual_dates)
        
        # Daily tick counts
        self.df['date'] = self.df['timestamp'].dt.date
        daily_counts = self.df.groupby('date').size()
        
        result = {
            'null_values': null_counts,
            'total_nulls': int(total_nulls),
            'duplicate_records': int(duplicate_count),
            'duplicate_percentage': round(duplicate_count / len(self.df) * 100, 4),
            'date_coverage': {
                'expected_days': len(date_range),
                'actual_days': len(actual_dates),
                'missing_days': len(missing_dates),
                'missing_dates': [str(d) for d in missing_dates[:20]]  # First 20
            },
            'daily_statistics': {
                'mean_ticks_per_day': float(daily_counts.mean()),
                'median_ticks_per_day': float(daily_counts.median()),
                'min_ticks_per_day': int(daily_counts.min()),
                'max_ticks_per_day': int(daily_counts.max()),
                'std_ticks_per_day': float(daily_counts.std())
            }
        }
        
        self.results['completeness'] = result
        return result
    
    def analyze_prices(self) -> Dict:
        """Analyze price data quality"""
        logger.info("Analyzing price data...")
        
        # Calculate spread
        self.df['spread'] = self.df['ask'] - self.df['bid']
        self.df['spread_pips'] = self.df['spread'] * 10000  # For EURUSD (adjust for JPY pairs)
        self.df['mid_price'] = (self.df['bid'] + self.df['ask']) / 2
        
        # Price statistics
        bid_stats = self.df['bid'].describe().to_dict()
        ask_stats = self.df['ask'].describe().to_dict()
        spread_stats = self.df['spread'].describe().to_dict()
        spread_pips_stats = self.df['spread_pips'].describe().to_dict()
        
        # Validation checks
        negative_spreads = (self.df['spread'] < 0).sum()
        zero_spreads = (self.df['spread'] == 0).sum()
        very_large_spreads = (self.df['spread_pips'] > 10).sum()
        
        # Outlier detection (IQR method)
        Q1_bid = self.df['bid'].quantile(0.25)
        Q3_bid = self.df['bid'].quantile(0.75)
        IQR_bid = Q3_bid - Q1_bid
        outlier_bid = ((self.df['bid'] < (Q1_bid - 3 * IQR_bid)) | 
                       (self.df['bid'] > (Q3_bid + 3 * IQR_bid))).sum()
        
        Q1_ask = self.df['ask'].quantile(0.25)
        Q3_ask = self.df['ask'].quantile(0.75)
        IQR_ask = Q3_ask - Q1_ask
        outlier_ask = ((self.df['ask'] < (Q1_ask - 3 * IQR_ask)) | 
                       (self.df['ask'] > (Q3_ask + 3 * IQR_ask))).sum()
        
        result = {
            'bid_statistics': {k: float(v) for k, v in bid_stats.items()},
            'ask_statistics': {k: float(v) for k, v in ask_stats.items()},
            'spread_statistics': {k: float(v) for k, v in spread_stats.items()},
            'spread_pips_statistics': {k: float(v) for k, v in spread_pips_stats.items()},
            'validation': {
                'negative_spreads': int(negative_spreads),
                'negative_spreads_percentage': round(negative_spreads / len(self.df) * 100, 4),
                'zero_spreads': int(zero_spreads),
                'zero_spreads_percentage': round(zero_spreads / len(self.df) * 100, 4),
                'very_large_spreads': int(very_large_spreads),
                'very_large_spreads_percentage': round(very_large_spreads / len(self.df) * 100, 4),
                'bid_outliers': int(outlier_bid),
                'bid_outliers_percentage': round(outlier_bid / len(self.df) * 100, 4),
                'ask_outliers': int(outlier_ask),
                'ask_outliers_percentage': round(outlier_ask / len(self.df) * 100, 4)
            }
        }
        
        self.results['prices'] = result
        return result
    
    def analyze_temporal(self) -> Dict:
        """Analyze temporal patterns and gaps"""
        logger.info("Analyzing temporal patterns...")
        
        # Time differences
        self.df['time_diff'] = self.df['timestamp'].diff()
        self.df['time_diff_seconds'] = self.df['time_diff'].dt.total_seconds()
        
        time_diff_stats = self.df['time_diff_seconds'].dropna().describe().to_dict()
        
        # Large gaps
        large_gaps = self.df[self.df['time_diff'] > timedelta(minutes=5)]
        weekend_gaps = large_gaps[large_gaps['timestamp'].dt.dayofweek >= 5]
        weekday_gaps = large_gaps[large_gaps['timestamp'].dt.dayofweek < 5]
        
        # Hourly analysis
        self.df['hour'] = self.df['timestamp'].dt.hour
        hourly_avg = self.df.groupby('hour').size() / len(self.df['date'].unique())
        
        # Tick frequency
        median_time_diff = self.df['time_diff_seconds'].median()
        ticks_per_second = 1 / median_time_diff if median_time_diff > 0 else 0
        ticks_per_minute = 60 / median_time_diff if median_time_diff > 0 else 0
        ticks_per_hour = 3600 / median_time_diff if median_time_diff > 0 else 0
        
        result = {
            'time_difference_statistics': {k: float(v) for k, v in time_diff_stats.items()},
            'tick_frequency': {
                'ticks_per_second': round(ticks_per_second, 2),
                'ticks_per_minute': round(ticks_per_minute, 2),
                'ticks_per_hour': round(ticks_per_hour, 2)
            },
            'gaps': {
                'large_gaps_total': int(len(large_gaps)),
                'weekend_gaps': int(len(weekend_gaps)),
                'weekday_gaps': int(len(weekday_gaps))
            },
            'hourly_distribution': {
                'peak_hour': int(hourly_avg.idxmax()),
                'peak_hour_ticks': float(hourly_avg.max()),
                'lowest_hour': int(hourly_avg.idxmin()),
                'lowest_hour_ticks': float(hourly_avg.min()),
                'mean_ticks_per_hour': float(hourly_avg.mean())
            }
        }
        
        # Top gaps
        if len(large_gaps) > 0:
            top_gaps = large_gaps.nlargest(10, 'time_diff')[['timestamp', 'time_diff']]
            result['top_gaps'] = [
                {
                    'timestamp': row['timestamp'].isoformat(),
                    'duration_seconds': row['time_diff'].total_seconds(),
                    'duration_hours': row['time_diff'].total_seconds() / 3600
                }
                for _, row in top_gaps.iterrows()
            ]
        
        self.results['temporal'] = result
        return result
    
    def analyze_statistics(self) -> Dict:
        """Perform statistical analysis"""
        logger.info("Performing statistical analysis...")
        
        # Price changes
        self.df['price_change'] = self.df['mid_price'].diff()
        self.df['price_change_pct'] = self.df['price_change'] / self.df['mid_price'].shift(1) * 100
        
        price_change_stats = self.df['price_change_pct'].dropna().describe().to_dict()
        
        # Daily volatility
        daily_volatility = self.df.groupby('date')['price_change_pct'].std()
        
        # Correlation
        correlation_cols = ['bid', 'ask', 'spread', 'spread_pips', 'time_diff_seconds']
        corr_matrix = self.df[correlation_cols].corr()
        
        result = {
            'price_change_statistics': {k: float(v) for k, v in price_change_stats.items()},
            'volatility': {
                'mean_daily_volatility': float(daily_volatility.mean()),
                'median_daily_volatility': float(daily_volatility.median()),
                'min_daily_volatility': float(daily_volatility.min()),
                'max_daily_volatility': float(daily_volatility.max())
            },
            'correlations': {
                col: {
                    other_col: float(corr_matrix.loc[col, other_col])
                    for other_col in correlation_cols
                }
                for col in correlation_cols
            }
        }
        
        self.results['statistics'] = result
        return result
    
    def calculate_quality_score(self) -> Dict:
        """Calculate overall quality score"""
        logger.info("Calculating quality score...")
        
        score = 100
        issues = []
        warnings_list = []
        
        # Check nulls
        if self.results['completeness']['total_nulls'] > 0:
            score -= 10
            issues.append("Null values present")
        
        # Check duplicates
        if self.results['completeness']['duplicate_percentage'] > 1:
            score -= 5
            issues.append("High duplicate rate")
        
        # Check negative spreads
        if self.results['prices']['validation']['negative_spreads'] > 0:
            score -= 20
            issues.append("Negative spreads detected")
        
        # Check weekday gaps
        if self.results['temporal']['gaps']['weekday_gaps'] > 10:
            score -= 10
            warnings_list.append("Many weekday gaps")
        
        # Check missing dates
        missing_pct = (self.results['completeness']['date_coverage']['missing_days'] / 
                      self.results['completeness']['date_coverage']['expected_days'] * 100)
        if missing_pct > 5:
            score -= 15
            issues.append(f"Many missing dates ({missing_pct:.1f}%)")
        
        # Check zero spreads
        if self.results['prices']['validation']['zero_spreads_percentage'] > 1:
            score -= 5
            warnings_list.append("High percentage of zero spreads")
        
        score = max(0, score)
        
        if score >= 90:
            status = "EXCELLENT"
        elif score >= 75:
            status = "GOOD"
        elif score >= 60:
            status = "ACCEPTABLE"
        else:
            status = "NEEDS_ATTENTION"
        
        result = {
            'score': score,
            'status': status,
            'issues': issues,
            'warnings': warnings_list
        }
        
        self.results['quality_score'] = result
        return result
    
    def create_visualizations(self):
        """Create visualization plots"""
        logger.info("Creating visualizations...")
        
        output_dir = self.output_dir / "quality_analysis"
        output_dir.mkdir(parents=True, exist_ok=True)
        
        # 1. Daily tick counts
        daily_counts = self.df.groupby('date').size()
        fig, ax = plt.subplots(figsize=(15, 6))
        ax.plot(daily_counts.index, daily_counts.values, marker='o', markersize=3, linewidth=1)
        ax.set_title(f'Daily Tick Count - {self.symbol}', fontsize=14, fontweight='bold')
        ax.set_xlabel('Date')
        ax.set_ylabel('Number of Ticks')
        ax.grid(True, alpha=0.3)
        plt.xticks(rotation=45)
        plt.tight_layout()
        plt.savefig(output_dir / 'daily_ticks.png', dpi=150, bbox_inches='tight')
        plt.close()
        
        # 2. Spread distribution
        fig, ax = plt.subplots(figsize=(12, 6))
        spread_pips_99 = self.df['spread_pips'].quantile(0.99)
        spread_data = self.df[self.df['spread_pips'] <= spread_pips_99]['spread_pips']
        ax.hist(spread_data, bins=100, alpha=0.7, color='steelblue', edgecolor='black')
        ax.axvline(self.df['spread_pips'].mean(), color='red', linestyle='--', linewidth=2, 
                  label=f'Mean: {self.df["spread_pips"].mean():.2f} pips')
        ax.axvline(self.df['spread_pips'].median(), color='green', linestyle='--', linewidth=2, 
                  label=f'Median: {self.df["spread_pips"].median():.2f} pips')
        ax.set_title(f'Spread Distribution (Pips) - {self.symbol}', fontsize=14, fontweight='bold')
        ax.set_xlabel('Spread (Pips)')
        ax.set_ylabel('Frequency')
        ax.legend()
        ax.grid(True, alpha=0.3, axis='y')
        plt.tight_layout()
        plt.savefig(output_dir / 'spread_distribution.png', dpi=150, bbox_inches='tight')
        plt.close()
        
        # 3. Hourly distribution
        hourly_avg = self.df.groupby('hour').size() / len(self.df['date'].unique())
        fig, ax = plt.subplots(figsize=(12, 6))
        ax.bar(hourly_avg.index, hourly_avg.values, color='steelblue', alpha=0.7)
        ax.set_title(f'Average Ticks per Hour - {self.symbol}', fontsize=14, fontweight='bold')
        ax.set_xlabel('Hour (UTC)')
        ax.set_ylabel('Average Ticks per Hour')
        ax.grid(True, alpha=0.3, axis='y')
        plt.tight_layout()
        plt.savefig(output_dir / 'hourly_distribution.png', dpi=150, bbox_inches='tight')
        plt.close()
        
        # 4. Daily average spread
        daily_spread = self.df.groupby('date')['spread_pips'].mean()
        fig, ax = plt.subplots(figsize=(15, 6))
        ax.plot(daily_spread.index, daily_spread.values, marker='o', markersize=3, linewidth=1)
        ax.set_title(f'Daily Average Spread (Pips) - {self.symbol}', fontsize=14, fontweight='bold')
        ax.set_xlabel('Date')
        ax.set_ylabel('Average Spread (Pips)')
        ax.grid(True, alpha=0.3)
        plt.xticks(rotation=45)
        plt.tight_layout()
        plt.savefig(output_dir / 'daily_spread.png', dpi=150, bbox_inches='tight')
        plt.close()
        
        logger.info(f"Visualizations saved to: {output_dir}")
    
    def generate_report(self, output_file: Optional[Path] = None) -> Dict:
        """Generate comprehensive analysis report"""
        logger.info("Generating analysis report...")
        
        # Run all analyses
        self.analyze_basic_info()
        self.analyze_completeness()
        self.analyze_prices()
        self.analyze_temporal()
        self.analyze_statistics()
        self.calculate_quality_score()
        
        # Create visualizations
        self.create_visualizations()
        
        # Compile full report
        report = {
            'analysis_date': datetime.now().isoformat(),
            'results': self.results
        }
        
        # Save report
        if output_file:
            output_file.parent.mkdir(parents=True, exist_ok=True)
            with open(output_file, 'w') as f:
                json.dump(report, f, indent=2)
            logger.info(f"Report saved to: {output_file}")
        
        return report
    
    def print_summary(self):
        """Print summary to console"""
        print(f"\n{'='*80}")
        print("DATA QUALITY ANALYSIS SUMMARY")
        print(f"{'='*80}")
        print(f"\nFile: {self.parquet_file}")
        print(f"Symbol: {self.symbol}")
        print(f"Total Records: {self.results['basic_info']['total_records']:,}")
        print(f"Date Range: {self.results['basic_info']['date_range']['start']} to {self.results['basic_info']['date_range']['end']}")
        
        print(f"\n{'-'*80}")
        print("QUALITY SCORE")
        print(f"{'-'*80}")
        qs = self.results['quality_score']
        print(f"Score: {qs['score']}/100")
        print(f"Status: {qs['status']}")
        if qs['issues']:
            print(f"Issues: {', '.join(qs['issues'])}")
        if qs['warnings']:
            print(f"Warnings: {', '.join(qs['warnings'])}")
        
        print(f"\n{'-'*80}")
        print("KEY METRICS")
        print(f"{'-'*80}")
        print(f"Mean Spread: {self.results['prices']['spread_pips_statistics']['mean']:.2f} pips")
        print(f"Negative Spreads: {self.results['prices']['validation']['negative_spreads']:,}")
        print(f"Weekday Gaps: {self.results['temporal']['gaps']['weekday_gaps']:,}")
        print(f"Missing Days: {self.results['completeness']['date_coverage']['missing_days']}")
        print(f"Average Ticks/Hour: {self.results['temporal']['tick_frequency']['ticks_per_hour']:.0f}")
        print(f"{'='*80}\n")


def parse_args():
    """Parse command-line arguments"""
    parser = argparse.ArgumentParser(
        description="Comprehensive Dukascopy data quality analysis",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Analyze specific file
  python analyze_dukascopy_data_quality.py --file data/dukascopy/EURUSD/2024.parquet

  # Analyze with custom output
  python analyze_dukascopy_data_quality.py --file data/dukascopy/EURUSD/2024.parquet --output report.json

  # Analyze all files for a symbol
  python analyze_dukascopy_data_quality.py --symbol EURUSD --data-dir data/dukascopy
        """
    )
    
    parser.add_argument(
        "--file",
        type=str,
        help="Path to parquet file to analyze"
    )
    parser.add_argument(
        "--symbol",
        type=str,
        help="Symbol to analyze (requires --data-dir)"
    )
    parser.add_argument(
        "--data-dir",
        type=str,
        default="data/dukascopy",
        help="Data directory (default: data/dukascopy)"
    )
    parser.add_argument(
        "--output",
        type=str,
        help="Output JSON report file path"
    )
    parser.add_argument(
        "--no-visualizations",
        action="store_true",
        help="Skip creating visualizations"
    )
    
    return parser.parse_args()


def main():
    """Main entry point"""
    args = parse_args()
    
    try:
        if args.file:
            # Analyze single file
            parquet_file = Path(args.file)
            symbol = parquet_file.parent.name
            
            analyzer = DataQualityAnalyzer(parquet_file, symbol)
            analyzer.load_data()
            
            output_file = Path(args.output) if args.output else None
            report = analyzer.generate_report(output_file)
            
            if not args.no_visualizations:
                analyzer.create_visualizations()
            
            analyzer.print_summary()
            
        elif args.symbol:
            # Analyze all files for a symbol
            data_dir = Path(args.data_dir)
            symbol_dir = data_dir / args.symbol.upper()
            
            if not symbol_dir.exists():
                logger.error(f"Symbol directory not found: {symbol_dir}")
                return 1
            
            parquet_files = sorted(symbol_dir.glob("*.parquet"))
            if not parquet_files:
                logger.error(f"No parquet files found in {symbol_dir}")
                return 1
            
            logger.info(f"Found {len(parquet_files)} parquet files for {args.symbol}")
            
            for parquet_file in parquet_files:
                logger.info(f"\nAnalyzing {parquet_file.name}...")
                analyzer = DataQualityAnalyzer(parquet_file, args.symbol.upper())
                analyzer.load_data()
                
                if not args.no_visualizations:
                    analyzer.create_visualizations()
                
                analyzer.print_summary()
        
        else:
            logger.error("Either --file or --symbol must be specified")
            return 1
        
        logger.info("[SUCCESS] Analysis complete")
        return 0
    
    except Exception as e:
        logger.error(f"Analysis failed: {e}", exc_info=True)
        return 1


if __name__ == "__main__":
    exit(main())
