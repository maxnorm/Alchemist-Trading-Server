"""
Parquet Converter Utility (Standalone)
NO dependencies on trading server
"""

import json
import pandas as pd
import pyarrow as pa
import pyarrow.parquet as pq
from pathlib import Path
from typing import Dict, List, Optional, Tuple
from datetime import datetime, timezone
import logging

logger = logging.getLogger(__name__)


class ParquetConverter:
    """Converts Dukascopy JSON tick data to Parquet format (standalone)"""

    def __init__(
        self,
        compression: str = "snappy",
        use_dictionary: bool = True,
        validate: bool = True
    ):
        self.compression = compression
        self.use_dictionary = use_dictionary
        self.validate = validate

    def load_dukascopy_json(self, json_path: Path) -> List[Dict]:
        """Load Dukascopy JSON file"""
        logger.info(f"Loading JSON file: {json_path}")

        try:
            with open(json_path, 'r', encoding='utf-8') as f:
                data = json.load(f)

            # Handle both array and object formats
            if isinstance(data, list):
                records = data
            elif isinstance(data, dict) and 'data' in data:
                records = data['data']
            else:
                raise ValueError(f"Unexpected JSON format in {json_path}")

            logger.info(f"Loaded {len(records)} records from {json_path}")
            return records

        except Exception as e:
            logger.error(f"Failed to load JSON file {json_path}: {e}")
            raise

    def parse_dukascopy_tick(
        self, record: Dict, symbol: str
    ) -> Optional[Tuple[datetime, float, float, str]]:
        """Parse single Dukascopy tick record"""
        try:
            # Dukascopy uses milliseconds since epoch
            timestamp_ms = record.get('time') or record.get('timestamp')
            if timestamp_ms is None:
                return None

            # Convert to datetime (UTC)
            timestamp = datetime.fromtimestamp(timestamp_ms / 1000.0, tz=timezone.utc)

            # Extract bid/ask - dukascopy-node uses bidPrice/askPrice
            # Support both formats for backward compatibility
            bid = float(record.get('bidPrice') or record.get('bid', 0))
            ask = float(record.get('askPrice') or record.get('ask', 0))

            # Basic validation
            if bid <= 0 or ask <= 0 or ask < bid:
                return None

            return (timestamp, bid, ask, symbol)

        except (ValueError, TypeError, KeyError):
            return None

    def json_to_dataframe(self, json_path: Path, symbol: str) -> pd.DataFrame:
        """Convert JSON file to pandas DataFrame"""
        records = self.load_dukascopy_json(json_path)

        parsed_ticks = []
        skipped = 0

        for record in records:
            tick = self.parse_dukascopy_tick(record, symbol)
            if tick:
                parsed_ticks.append(tick)
            else:
                skipped += 1

        if skipped > 0:
            logger.warning(f"Skipped {skipped} invalid records")

        if not parsed_ticks:
            raise ValueError(f"No valid ticks found in {json_path}")

        # Create DataFrame
        df = pd.DataFrame(
            parsed_ticks,
            columns=['timestamp', 'bid', 'ask', 'symbol']
        )

        # Optimize dtypes
        df['timestamp'] = pd.to_datetime(df['timestamp'], utc=True)
        df['bid'] = df['bid'].astype('float64')
        df['ask'] = df['ask'].astype('float64')
        df['symbol'] = df['symbol'].astype('category')

        # Sort by timestamp
        df = df.sort_values('timestamp').reset_index(drop=True)

        logger.info(f"Created DataFrame with {len(df)} ticks")
        return df

    def validate_dataframe(self, df: pd.DataFrame, symbol: str) -> Dict:
        """Quick validation during conversion"""
        errors = []
        warnings = []

        # Check for negative spreads
        negative_spreads = (df['ask'] < df['bid']).sum()
        if negative_spreads > 0:
            errors.append(f"{negative_spreads} negative spreads detected")

        # Check for nulls
        nulls = df.isnull().sum().sum()
        if nulls > 0:
            errors.append(f"{nulls} null values detected")

        # Check timestamp order
        if not df['timestamp'].is_monotonic_increasing:
            errors.append("Timestamps not in chronological order")

        # Check for extreme values
        if df['bid'].min() < 0.0001 or df['ask'].min() < 0.0001:
            warnings.append("Extremely low prices detected")

        if df['bid'].max() > 1000000 or df['ask'].max() > 1000000:
            warnings.append("Extremely high prices detected")

        # Check spread statistics
        spread = df['ask'] - df['bid']
        mean_spread = spread.mean()
        std_spread = spread.std()

        if mean_spread < 0:
            errors.append(f"Negative mean spread: {mean_spread}")

        if std_spread > mean_spread * 10:
            warnings.append(f"High spread volatility: std={std_spread:.6f}, mean={mean_spread:.6f}")

        return {
            'passed': len(errors) == 0,
            'errors': errors,
            'warnings': warnings,
            'stats': {
                'mean_spread': float(mean_spread),
                'std_spread': float(std_spread),
                'min_bid': float(df['bid'].min()),
                'max_bid': float(df['bid'].max()),
                'min_ask': float(df['ask'].min()),
                'max_ask': float(df['ask'].max())
            }
        }

    def partition_by_year(self, df: pd.DataFrame) -> Dict[int, pd.DataFrame]:
        """Partition DataFrame by year"""
        df['year'] = df['timestamp'].dt.year
        partitions = {}

        for year, group_df in df.groupby('year'):
            partition_df = group_df.drop(columns=['year']).copy()
            partitions[year] = partition_df

        logger.info(f"Created {len(partitions)} yearly partitions")
        return partitions

    def write_parquet(
        self,
        df: pd.DataFrame,
        output_path: Path,
        metadata: Optional[Dict] = None
    ) -> None:
        """Write DataFrame to Parquet file"""
        # Create PyArrow Table
        table = pa.Table.from_pandas(df)

        # Add metadata
        if metadata:
            metadata_json = {k: json.dumps(v) if not isinstance(v, str) else v
                           for k, v in metadata.items()}
            existing_metadata = table.schema.metadata or {}
            combined_metadata = {**existing_metadata, **metadata_json}
            table = table.replace_schema_metadata(combined_metadata)

        # Write with compression
        pq.write_table(
            table,
            output_path,
            compression=self.compression,
            use_dictionary=self.use_dictionary,
            version='2.6'
        )

        file_size_mb = output_path.stat().st_size / (1024 * 1024)
        logger.info(f"Wrote Parquet file: {output_path} ({file_size_mb:.2f} MB)")

    def json_to_parquet(
        self,
        json_path: Path,
        output_dir: Path,
        symbol: str
    ) -> Dict[str, Path]:
        """Convert JSON ticks to Parquet files (yearly partitions)"""
        logger.info(f"Converting {json_path} to Parquet (symbol: {symbol})")

        # Create output directory
        output_dir.mkdir(parents=True, exist_ok=True)

        # Load and convert to DataFrame
        df = self.json_to_dataframe(json_path, symbol)

        # Validate if enabled
        if self.validate:
            validation_result = self.validate_dataframe(df, symbol)
            if not validation_result['passed']:
                error_msg = '; '.join(validation_result['errors'])
                raise ValueError(f"Validation failed: {error_msg}")
            if validation_result['warnings']:
                for warning in validation_result['warnings']:
                    logger.warning(f"[{symbol}] {warning}")

        # Partition by year
        partitions = self.partition_by_year(df)

        parquet_files = {}
        for year, partition_df in partitions.items():
            output_file = output_dir / f"{year}.parquet"

            metadata = {
                'symbol': symbol,
                'year': str(year),
                'source': 'dukascopy',
                'converted_at': datetime.now(timezone.utc).isoformat(),
                'tick_count': str(len(partition_df)),
                'start_date': partition_df['timestamp'].min().isoformat(),
                'end_date': partition_df['timestamp'].max().isoformat()
            }

            self.write_parquet(partition_df, output_file, metadata)
            parquet_files[str(year)] = output_file

        # Create metadata file
        self.create_metadata(parquet_files, symbol, output_dir)

        return parquet_files

    def create_metadata(
        self,
        parquet_files: Dict[str, Path],
        symbol: str,
        output_dir: Path
    ) -> Path:
        """Create metadata JSON for dataset"""
        metadata = {
            'symbol': symbol,
            'source': 'dukascopy',
            'created_at': datetime.now(timezone.utc).isoformat(),
            'years': sorted(parquet_files.keys()),
            'files': {year: str(path.name) for year, path in parquet_files.items()},
            'compression': self.compression
        }

        metadata_path = output_dir / 'metadata.json'
        with open(metadata_path, 'w', encoding='utf-8') as f:
            json.dump(metadata, f, indent=2)

        logger.info(f"Created metadata file: {metadata_path}")
        return metadata_path
