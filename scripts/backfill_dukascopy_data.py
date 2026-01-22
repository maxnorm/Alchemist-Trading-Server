#!/usr/bin/env python3
"""
Standalone Dukascopy Historical Data Collection Script
NO dependencies on trading server - runs completely standalone

Dependencies: pandas, pyarrow, numpy (standard data science stack)
"""

import argparse
import sys
import os
import subprocess
import tempfile
import shutil
import json
import logging
from pathlib import Path
from datetime import datetime, timedelta, timezone
from typing import List, Dict, Optional, Tuple
import time
import platform

# Standalone imports - NO trading server dependencies
import pandas as pd
import pyarrow as pa
import pyarrow.parquet as pq

# Setup logging with file handler
log_file_path = Path('logs/dukascopy_backfill.log')
log_file_path.parent.mkdir(parents=True, exist_ok=True)

# Create file handler with append mode
file_handler = logging.FileHandler(log_file_path, mode='a', encoding='utf-8')
file_handler.setLevel(logging.DEBUG)  # Capture everything in file

# Create console handler
console_handler = logging.StreamHandler()
console_handler.setLevel(logging.INFO)  # Only INFO+ to console

# Formatter
formatter = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')
file_handler.setFormatter(formatter)
console_handler.setFormatter(formatter)

# Setup root logger
root_logger = logging.getLogger()
root_logger.setLevel(logging.DEBUG)
root_logger.addHandler(file_handler)
root_logger.addHandler(console_handler)

logger = logging.getLogger('dukascopy_backfill')


class TeeLogger:
    """Tee output to both log file and original stream"""
    def __init__(self, original_stream, log_level=logging.INFO):
        self.original_stream = original_stream
        self.log_level = log_level
        self.logger = logging.getLogger('dukascopy_backfill.stdout')
    
    def write(self, message):
        try:
            if message and message.strip():  # Only log non-empty lines
                self.logger.log(self.log_level, message.rstrip())
        except Exception:
            # If logging fails, at least write to original stream
            pass
        try:
            self.original_stream.write(message)
            self.original_stream.flush()
        except Exception:
            pass
    
    def flush(self):
        try:
            self.original_stream.flush()
        except Exception:
            pass
    
    def isatty(self):
        try:
            return self.original_stream.isatty()
        except Exception:
            return False

# Default supported pairs from database
DEFAULT_PAIRS = [
    'EURUSD', 'GBPUSD', 'USDJPY', 'AUDUSD', 'NZDUSD', 'USDCHF', 'USDCAD',  # Majors
    'EURGBP', 'EURJPY', 'EURAUD', 'EURNZD', 'EURCHF', 'EURCAD',  # EUR crosses
    'GBPJPY', 'GBPAUD', 'GBPNZD', 'GBPCHF', 'GBPCAD',  # GBP crosses
    'AUDJPY', 'NZDJPY', 'CHFJPY', 'CADJPY',  # JPY crosses
    'AUDNZD', 'AUDCHF', 'AUDCAD', 'NZDCHF', 'NZDCAD', 'CADCHF',  # Other crosses
    'XAUUSD', 'XAUEUR'  # Gold pairs
]


class ProgressTracker:
    """Simple JSON file-based progress tracker for resumable downloads"""
    
    def __init__(self, progress_file: str = "data/.dukascopy_progress.json"):
        self.progress_file = Path(progress_file)
        self.progress = self._load()
    
    def _load(self) -> Dict:
        """Load progress from JSON file"""
        if self.progress_file.exists():
            try:
                with open(self.progress_file, 'r') as f:
                    return json.load(f)
            except Exception as e:
                logger.warning(f"Could not load progress file: {e}")
                return {}
        return {}
    
    def save(self):
        """Save progress to JSON file"""
        try:
            self.progress_file.parent.mkdir(parents=True, exist_ok=True)
            with open(self.progress_file, 'w') as f:
                json.dump(self.progress, f, indent=2)
        except Exception as e:
            logger.warning(f"Could not save progress file: {e}")
    
    def mark_started(self, symbol: str, start_date: datetime, end_date: datetime):
        """Mark a download as started"""
        if symbol not in self.progress:
            self.progress[symbol] = {}
        
        self.progress[symbol]['_current'] = {
            'status': 'in_progress',
            'start_date': start_date.isoformat(),
            'end_date': end_date.isoformat(),
            'started_at': datetime.now().isoformat()
        }
        self.save()
    
    def mark_completed(self, symbol: str, year: int, file_path: str):
        """Mark a specific year as completed"""
        if symbol not in self.progress:
            self.progress[symbol] = {}
        
        self.progress[symbol][str(year)] = {
            'status': 'completed',
            'file_path': file_path,
            'completed_at': datetime.now().isoformat()
        }
        self.save()
    
    def mark_failed(self, symbol: str, error: str):
        """Mark a download as failed"""
        if symbol not in self.progress:
            self.progress[symbol] = {}
        
        self.progress[symbol]['_current'] = {
            'status': 'failed',
            'error': error,
            'failed_at': datetime.now().isoformat()
        }
        self.save()
    
    def is_completed(self, symbol: str, year: int) -> bool:
        """Check if a specific year is already completed"""
        return (symbol in self.progress and 
                str(year) in self.progress[symbol] and
                self.progress[symbol][str(year)].get('status') == 'completed')
    
    def get_completed_years(self, symbol: str) -> List[int]:
        """Get list of completed years for a symbol"""
        if symbol not in self.progress:
            return []
        
        completed = []
        for key, value in self.progress[symbol].items():
            if key.startswith('_'):  # Skip metadata keys
                continue
            if value.get('status') == 'completed':
                try:
                    completed.append(int(key))
                except ValueError:
                    continue
        
        return sorted(completed)


class ParquetConverter:
    """Convert Dukascopy JSON to Parquet format with validation"""
    
    def __init__(self, compression: str = "snappy", validate: bool = True):
        self.compression = compression
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
    
    def parse_dukascopy_tick(self, record: Dict, symbol: str) -> Optional[Tuple]:
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
        
        except (ValueError, TypeError, KeyError) as e:
            logger.debug(f"Failed to parse tick record: {e}")
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
        
        return {
            'passed': len(errors) == 0,
            'errors': errors,
            'warnings': warnings
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
    
    def write_parquet(self, df: pd.DataFrame, output_path: Path, metadata: Optional[Dict] = None):
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
            use_dictionary=True,
            version='2.6'
        )
        
        file_size_mb = output_path.stat().st_size / (1024 * 1024)
        logger.info(f"Wrote Parquet file: {output_path} ({file_size_mb:.2f} MB)")
    
    def json_to_parquet(self, json_path: Path, output_dir: Path, symbol: str) -> Dict[str, Path]:
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
                raise ValueError(f"Validation failed: {validation_result['errors']}")
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
        
        return parquet_files


def find_dukascopy_command() -> Tuple[Optional[List[str]], bool]:
    """
    Find dukascopy-node command with priority order
    
    Returns: (command_list, use_shell)
    """
    is_windows = platform.system() == 'Windows'
    
    # Priority 1: Local node_modules
    local_paths = []
    if is_windows:
        local_paths = [
            os.path.join(os.getcwd(), "node_modules", ".bin", "dukascopy-node.cmd"),
            os.path.join(os.getcwd(), "node_modules", ".bin", "dukascopy-node")
        ]
    else:
        local_paths = [
            os.path.join(os.getcwd(), "node_modules", ".bin", "dukascopy-node")
        ]
    
    for cmd_path in local_paths:
        if os.path.exists(cmd_path):
            try:
                result = subprocess.run(
                    [cmd_path, "--help"],
                    capture_output=True,
                    timeout=10,
                    shell=True
                )
                if result.returncode == 0:
                    logger.info(f"[OK] Found local installation: {cmd_path}")
                    return [cmd_path], True
            except Exception as e:
                logger.debug(f"Local installation test failed: {e}")
    
    # Priority 2: npx (automatic download)
    try:
        result = subprocess.run(
            ["npx", "dukascopy-node", "--help"],
            capture_output=True,
            timeout=10
        )
        if result.returncode == 0:
            logger.info("[OK] Found npx installation")
            return ["npx", "dukascopy-node"], False
    except Exception as e:
        logger.debug(f"npx test failed: {e}")
    
    # Priority 3: Global installation
    try:
        result = subprocess.run(
            ["dukascopy-node", "--help"],
            capture_output=True,
            timeout=10
        )
        if result.returncode == 0:
            logger.info("[OK] Found global installation")
            return ["dukascopy-node"], False
    except Exception as e:
        logger.debug(f"Global installation test failed: {e}")
    
    return None, False


def check_dukascopy_cli() -> bool:
    """Check if dukascopy-node CLI is available"""
    cmd, _ = find_dukascopy_command()
    return cmd is not None


def parse_date(date_str: str) -> datetime:
    """Parse date string to datetime object (UTC)"""
    try:
        return datetime.strptime(date_str, "%Y-%m-%d").replace(tzinfo=timezone.utc)
    except ValueError as e:
        raise ValueError(f"Invalid date format: {date_str}. Use YYYY-MM-DD.") from e


def download_dukascopy_data(
    symbol: str,
    start_date: datetime,
    end_date: datetime,
    temp_dir: Path,
    batch_size: int = 3,
    pause_ms: int = 5000,
    max_retries: int = 3,
    verbose: bool = False
) -> Optional[Path]:
    """Download data from Dukascopy using dukascopy-node CLI"""
    logger.info(f"[{symbol}] Downloading from {start_date.date()} to {end_date.date()}")
    
    # Dukascopy symbol format is lowercase
    duka_symbol = symbol.lower()
    
    # Format dates
    start_str = start_date.strftime("%Y-%m-%d")
    end_str = end_date.strftime("%Y-%m-%d")
    
    # Find command
    cmd_base, use_shell = find_dukascopy_command()
    if not cmd_base:
        logger.error(f"[{symbol}] Could not find dukascopy-node command")
        return None
    
    # Build full command
    cmd = cmd_base + [
        "-i", duka_symbol,
        "-from", start_str,
        "-to", end_str,
        "-t", "tick",
        "-f", "json",
        "-dir", str(temp_dir),
        "-bs", str(batch_size),
        "-bp", str(pause_ms),
        "--cache"  # Enable cache for resumable downloads
    ]
    
    # Add debug flag if verbose
    if verbose:
        cmd.append("--debug")
    
    logger.info(f"[{symbol}] Command: {' '.join(cmd)}")
    
    # Retry logic
    process = None
    for attempt in range(1, max_retries + 1):
        try:
            logger.info(f"[{symbol}] Download attempt {attempt}/{max_retries}")
            
            if verbose:
                # Stream output in real-time for verbose mode
                logger.info(f"[{symbol}] Starting download (verbose mode - output will stream below)")
                process = subprocess.Popen(
                    cmd,
                    stdout=subprocess.PIPE,
                    stderr=subprocess.STDOUT,
                    text=True,
                    bufsize=1,
                    shell=use_shell,
                    universal_newlines=True
                )
                
                # Stream output line by line with timeout protection using threading
                import queue
                import threading
                
                last_progress_time = time.time()
                start_time = time.time()
                max_silence_seconds = 600  # 10 minutes without output (conversion can be slow)
                download_timeout = 3600 * 6  # 6 hours max total time
                conversion_phase_detected = False
                
                output_queue = queue.Queue()
                output_done = threading.Event()
                
                def read_output(stream, q, done_event):
                    """Read output in background thread and log everything to file"""
                    try:
                        for line in iter(stream.readline, ''):
                            if line:
                                line_stripped = line.strip()
                                if line_stripped:
                                    # Log all output to file
                                    logger.info(f"[{symbol}] [STDOUT] {line_stripped}")
                                q.put(line)
                            if not line and stream.closed:
                                break
                    except Exception as e:
                        logger.error(f"[{symbol}] Output reader error: {e}", exc_info=True)
                    finally:
                        done_event.set()
                        q.put(None)  # Signal end
                
                # Start background reader thread
                reader_thread = threading.Thread(
                    target=read_output,
                    args=(process.stdout, output_queue, output_done),
                    daemon=True
                )
                reader_thread.start()
                
                # Read from queue with timeout checks and file monitoring
                last_file_size = 0
                last_file_check = time.time()
                file_check_interval = 30  # Check file size every 30 seconds
                files_downloaded_count = 0
                last_download_time = time.time()
                
                while process.poll() is None or not output_done.is_set():
                    # Check overall timeout
                    if time.time() - start_time > download_timeout:
                        logger.error(f"[{symbol}] Download timeout after {download_timeout/3600:.1f} hours")
                        process.terminate()
                        time.sleep(5)
                        if process.poll() is None:
                            process.kill()
                        break
                    
                    # Monitor output file size to detect progress even without stdout
                    current_time = time.time()
                    if current_time - last_file_check > file_check_interval:
                        json_files = list(temp_dir.glob(f"{duka_symbol}*.json"))
                        if json_files:
                            current_file_size = json_files[0].stat().st_size
                            if current_file_size > last_file_size:
                                # File is growing - process is making progress
                                last_file_size = current_file_size
                                last_progress_time = current_time
                                file_size_mb = current_file_size / (1024 * 1024)
                                logger.debug(f"[{symbol}] File growing: {file_size_mb:.2f} MB (silent progress)")
                        last_file_check = current_time
                    
                    # Try to read line with timeout
                    try:
                        line = output_queue.get(timeout=10)  # 10 second timeout per line
                        if line is None:  # End signal
                            break
                        if line:
                            line = line.strip()
                            if line:
                                # Output already logged by reader thread, just track progress
                                last_progress_time = time.time()
                                # Detect if we're in download phase (network/cache messages)
                                if "network" in line.lower() or "cache" in line.lower():
                                    files_downloaded_count += 1
                                    last_download_time = time.time()
                                    conversion_phase_detected = False
                                # Detect conversion phase (no more download messages)
                                elif files_downloaded_count > 0 and time.time() - last_download_time > 60:
                                    if not conversion_phase_detected:
                                        logger.info(f"[{symbol}] Download phase complete ({files_downloaded_count} files), entering conversion phase...")
                                        conversion_phase_detected = True
                                        # Reset silence timer for conversion phase (can take longer)
                                        last_progress_time = time.time()
                    except queue.Empty:
                        # No output for 10 seconds, check if process is hung
                        elapsed_silence = time.time() - last_progress_time
                        
                        # Adjust timeout based on phase
                        effective_timeout = max_silence_seconds
                        if conversion_phase_detected:
                            # Conversion phase can take longer - allow 20 minutes
                            effective_timeout = 1200  # 20 minutes for conversion
                            phase_info = " (conversion phase - slower)"
                        else:
                            phase_info = " (download phase)"
                        
                        if elapsed_silence > effective_timeout:
                            logger.warning(f"[{symbol}] No output for {elapsed_silence:.0f}s{phase_info}, checking process...")
                            if process.poll() is None:
                                logger.warning(f"[{symbol}] Process still running but silent, may be hung")
                                # Check if reader thread is still alive
                                if not reader_thread.is_alive():
                                    logger.error(f"[{symbol}] Reader thread died, process may have crashed")
                                    process.terminate()
                                    time.sleep(5)
                                    if process.poll() is None:
                                        process.kill()
                                    break
                                
                                # Check if final JSON file exists (conversion complete)
                                json_files = list(temp_dir.glob(f"{duka_symbol}*.json"))
                                if json_files:
                                    current_file_size = json_files[0].stat().st_size
                                    if current_file_size > last_file_size:
                                        # File grew - process is working, reset timer
                                        logger.info(f"[{symbol}] File grew from {last_file_size} to {current_file_size} bytes - process is working")
                                        last_file_size = current_file_size
                                        last_progress_time = time.time()
                                        continue
                                    elif current_file_size > 0 and conversion_phase_detected:
                                        # File exists and we're in conversion - might be finalizing
                                        logger.info(f"[{symbol}] JSON file exists ({current_file_size} bytes), conversion may be finalizing...")
                                        # Give it more time if file exists
                                        if elapsed_silence < effective_timeout + 300:  # Extra 5 minutes
                                            continue
                                
                                # No file growth and timeout exceeded - likely hung
                                time.sleep(60)
                                if time.time() - last_progress_time > effective_timeout + 60:
                                    logger.error(f"[{symbol}] Process appears hung after {effective_timeout + 60}s silence{phase_info}, terminating")
                                    process.terminate()
                                    time.sleep(5)
                                    if process.poll() is None:
                                        process.kill()
                                    break
                        continue
                
                # Wait for process to complete (with timeout)
                try:
                    returncode = process.wait(timeout=30)
                except subprocess.TimeoutExpired:
                    logger.warning(f"[{symbol}] Process didn't terminate quickly, checking status...")
                    returncode = process.poll()
                    if returncode is None:
                        logger.error(f"[{symbol}] Process still running, forcing termination")
                        process.terminate()
                        time.sleep(5)
                        if process.poll() is None:
                            process.kill()
                        returncode = process.poll() or -1
                
                # Check for downloaded file
                json_files = list(temp_dir.glob(f"{duka_symbol}*.json"))
                if returncode == 0:
                    if json_files:
                        downloaded_file = json_files[0]
                        file_size_mb = downloaded_file.stat().st_size / (1024 * 1024)
                        logger.info(f"[{symbol}] Downloaded successfully: {downloaded_file} ({file_size_mb:.2f} MB)")
                        return downloaded_file
                    else:
                        logger.error(f"[{symbol}] Download succeeded but no JSON file found")
                        continue
                else:
                    logger.error(f"[{symbol}] Download failed (exit code {returncode})")
                    continue
            else:
                # Non-verbose: capture output and log everything to file, show periodic progress to console
                logger.info(f"[{symbol}] Download in progress... (this may take 2-4 hours)")
                start_time = time.time()
                last_progress_log = start_time
                
                process = subprocess.Popen(
                    cmd,
                    stdout=subprocess.PIPE,
                    stderr=subprocess.STDOUT,  # Merge stderr into stdout
                    text=True,
                    shell=use_shell,
                    bufsize=1,
                    universal_newlines=True
                )
                
                # Capture all output in background thread and log to file
                import queue
                import threading
                
                output_queue = queue.Queue()
                output_done = threading.Event()
                
                def read_output(stream, q, done_event):
                    """Read output in background thread and log everything"""
                    try:
                        for line in iter(stream.readline, ''):
                            if line:
                                line = line.strip()
                                if line:
                                    # Log all output to file at INFO level
                                    logger.info(f"[{symbol}] [STDOUT] {line}")
                                q.put(line)
                            if not line and stream.closed:
                                break
                    except Exception as e:
                        logger.error(f"[{symbol}] Output reader error: {e}", exc_info=True)
                    finally:
                        done_event.set()
                        q.put(None)  # Signal end
                
                # Start background reader thread
                reader_thread = threading.Thread(
                    target=read_output,
                    args=(process.stdout, output_queue, output_done),
                    daemon=True
                )
                reader_thread.start()
                
                # Monitor progress periodically with timeout protection
                download_timeout = 3600 * 6  # 6 hours max
                last_file_size = 0
                no_progress_count = 0
                max_no_progress_checks = 20  # 20 * 30s = 10 minutes without growth
                
                while process.poll() is None or not output_done.is_set():
                    elapsed = time.time() - start_time
                    
                    # Check for overall timeout
                    if elapsed > download_timeout:
                        logger.error(f"[{symbol}] Download timeout after {download_timeout/3600:.1f} hours")
                        process.terminate()
                        time.sleep(5)
                        if process.poll() is None:
                            process.kill()
                        break
                    
                    # Drain output queue (already logged by reader thread)
                    try:
                        while True:
                            line = output_queue.get_nowait()
                            if line is None:  # End signal
                                break
                    except queue.Empty:
                        pass
                    
                    # Check for growing files in temp directory
                    json_files = list(temp_dir.glob(f"{duka_symbol}*.json"))
                    if json_files:
                        file_size = json_files[0].stat().st_size
                        file_size_mb = file_size / (1024 * 1024)
                        
                        # Check if file is growing
                        if file_size > last_file_size:
                            last_file_size = file_size
                            no_progress_count = 0
                            logger.info(f"[{symbol}] Progress: {file_size_mb:.2f} MB downloaded (elapsed: {int(elapsed/60)}m {int(elapsed%60)}s)")
                        else:
                            no_progress_count += 1
                            if no_progress_count >= max_no_progress_checks:
                                logger.warning(f"[{symbol}] No file growth for {max_no_progress_checks * 30}s, process may be hung")
                                if process.poll() is None:
                                    logger.error(f"[{symbol}] Terminating hung process")
                                    process.terminate()
                                    time.sleep(5)
                                    if process.poll() is None:
                                        process.kill()
                                    break
                            elif time.time() - last_progress_log > 300:  # Log every 5 minutes
                                logger.info(f"[{symbol}] Still downloading... {file_size_mb:.2f} MB (elapsed: {int(elapsed/60)}m {int(elapsed%60)}s)")
                                last_progress_log = time.time()
                    elif time.time() - last_progress_log > 300:  # Log every 5 minutes
                        logger.info(f"[{symbol}] Still downloading... (elapsed: {int(elapsed/60)}m {int(elapsed%60)}s)")
                        last_progress_log = time.time()
                    
                    time.sleep(30)  # Check every 30 seconds
                
                # Drain any remaining output
                try:
                    while True:
                        line = output_queue.get_nowait()
                        if line is None:
                            break
                except queue.Empty:
                    pass
                
                # Process finished, get return code
                returncode = process.returncode
                
                if returncode == 0:
                    # Find the downloaded file
                    json_files = list(temp_dir.glob(f"{duka_symbol}*.json"))
                    if json_files:
                        downloaded_file = json_files[0]
                        file_size_mb = downloaded_file.stat().st_size / (1024 * 1024)
                        logger.info(f"[{symbol}] Downloaded successfully: {downloaded_file} ({file_size_mb:.2f} MB)")
                        return downloaded_file
                    else:
                        logger.error(f"[{symbol}] Download succeeded but no JSON file found")
                else:
                    logger.error(f"[{symbol}] Download failed (exit code {returncode})")
                    
                    # Get any remaining output for error analysis
                    try:
                        stdout, stderr = process.communicate(timeout=5)
                        if stdout:
                            logger.error(f"[{symbol}] Remaining STDOUT: {stdout}")
                        if stderr:
                            logger.error(f"[{symbol}] Remaining STDERR: {stderr}")
                    except subprocess.TimeoutExpired:
                        pass
                    
                    # Check for specific error types (output already logged above)
                    # Rate limiting
                    if "429" in str(returncode) or "rate limit" in str(returncode).lower():
                        wait_time = 60 * (2 ** attempt)  # Exponential backoff
                        logger.warning(f"[{symbol}] Rate limited, waiting {wait_time}s")
                        time.sleep(wait_time)
                        continue
                    
                    # Connection reset (ECONNRESET)
                    if "econnreset" in str(returncode).lower() or "connection reset" in str(returncode).lower():
                        wait_time = 30 * attempt  # Progressive backoff
                        logger.warning(f"[{symbol}] Connection reset detected, waiting {wait_time}s before retry")
                        time.sleep(wait_time)
                        continue
                    
                    # Network timeout
                    if "timeout" in str(returncode).lower() or "etimedout" in str(returncode).lower():
                        wait_time = 20 * attempt
                        logger.warning(f"[{symbol}] Network timeout, waiting {wait_time}s before retry")
                        time.sleep(wait_time)
                        continue
            
        
        except subprocess.TimeoutExpired:
            logger.error(f"[{symbol}] Download timed out")
            if process and process.poll() is None:
                try:
                    process.terminate()
                    time.sleep(5)
                    if process.poll() is None:
                        process.kill()
                except:
                    pass
        except KeyboardInterrupt:
            logger.warning(f"[{symbol}] Interrupted by user")
            if process and process.poll() is None:
                try:
                    process.terminate()
                    time.sleep(2)
                    if process.poll() is None:
                        process.kill()
                except:
                    pass
            raise
        except Exception as e:
            logger.error(f"[{symbol}] Download error: {e}", exc_info=True)
            if process and process.poll() is None:
                try:
                    process.terminate()
                    time.sleep(2)
                    if process.poll() is None:
                        process.kill()
                except:
                    pass
        
        if attempt < max_retries:
            # Exponential backoff with jitter
            base_wait = 30 * (2 ** (attempt - 1))  # 30s, 60s, 120s
            jitter = time.time() % 10  # Add up to 10s jitter
            wait_time = base_wait + jitter
            logger.info(f"[{symbol}] Retrying in {wait_time:.0f}s... (attempt {attempt + 1}/{max_retries})")
            time.sleep(wait_time)
    
    logger.error(f"[{symbol}] Failed after {max_retries} attempts")
    return None


def process_symbol(
    symbol: str,
    start_date: datetime,
    end_date: datetime,
    output_dir: Path,
    batch_size: int,
    pause_ms: int,
    compression: str,
    keep_json: bool,
    progress_tracker: ProgressTracker,
    verbose: bool = False
) -> Dict:
    """Process a single symbol: download + convert to Parquet"""
    logger.info(f"[{symbol}] Processing symbol")
    
    result = {
        'symbol': symbol,
        'status': 'pending',
        'parquet_files': {},
        'error': None,
        'start_time': datetime.now(timezone.utc),
        'end_time': None
    }
    
    # Mark as started
    progress_tracker.mark_started(symbol, start_date, end_date)
    
    # Create temp directory
    temp_dir = Path(tempfile.mkdtemp(prefix=f"dukascopy_{symbol}_"))
    
    try:
        # Download from Dukascopy
        json_file = download_dukascopy_data(
            symbol,
            start_date,
            end_date,
            temp_dir,
            batch_size,
            pause_ms,
            verbose=verbose
        )
        
        if json_file is None:
            raise Exception("Download failed")
        
        # Convert to Parquet
        converter = ParquetConverter(compression=compression)
        symbol_dir = output_dir / symbol
        parquet_files = converter.json_to_parquet(json_file, symbol_dir, symbol)
        
        # Mark each year as completed
        for year_str, file_path in parquet_files.items():
            progress_tracker.mark_completed(symbol, int(year_str), str(file_path))
        
        result['parquet_files'] = parquet_files
        result['status'] = 'completed'
        
        logger.info(f"[{symbol}] Completed successfully")
    
    except Exception as e:
        result['status'] = 'failed'
        result['error'] = str(e)
        progress_tracker.mark_failed(symbol, str(e))
        logger.error(f"[{symbol}] Failed: {e}", exc_info=True)
    
    finally:
        result['end_time'] = datetime.now(timezone.utc)
        
        # Cleanup
        if not keep_json and temp_dir.exists():
            try:
                shutil.rmtree(temp_dir)
                logger.info(f"[{symbol}] Cleaned up temporary files")
            except Exception as e:
                logger.warning(f"[{symbol}] Cleanup failed: {e}")
    
    return result


def backfill_multiple_symbols(
    pairs: List[str],
    start_date: datetime,
    end_date: datetime,
    output_dir: Path,
    batch_size: int,
    pause_ms: int,
    compression: str,
    keep_json: bool,
    resume: bool,
    verbose: bool = False
) -> Dict[str, Dict]:
    """Backfill multiple symbols"""
    logger.info("=" * 80)
    logger.info("DUKASCOPY HISTORICAL DATA BACKFILL (STANDALONE)")
    logger.info(f"Pairs: {len(pairs)}")
    logger.info(f"Date Range: {start_date.date()} to {end_date.date()}")
    logger.info(f"Output: {output_dir}")
    logger.info(f"Rate Limiting: batch_size={batch_size}, pause={pause_ms}ms")
    logger.info("=" * 80)
    
    # Initialize progress tracker
    progress_tracker = ProgressTracker()
    
    results = {}
    start_time = datetime.now(timezone.utc)
    
    # Process each symbol
    for i, symbol in enumerate(pairs, 1):
        logger.info(f"\n[{i}/{len(pairs)}] Processing {symbol}")
        
        # Check if already completed (resume)
        if resume:
            completed_years = progress_tracker.get_completed_years(symbol)
            if completed_years:
                logger.info(f"[{symbol}] Already completed years: {completed_years}")
                # Could implement partial resume here if needed
        
        result = process_symbol(
            symbol,
            start_date,
            end_date,
            output_dir,
            batch_size,
            pause_ms,
            compression,
            keep_json,
            progress_tracker,
            verbose
        )
        
        results[symbol] = result
        
        # Log progress
        completed = sum(1 for r in results.values() if r['status'] == 'completed')
        failed = sum(1 for r in results.values() if r['status'] == 'failed')
        
        logger.info(f"Progress: {completed} completed, {failed} failed")
    
    # Final summary
    elapsed = datetime.now(timezone.utc) - start_time
    logger.info("=" * 80)
    logger.info("BACKFILL SUMMARY")
    logger.info(f"Total Time: {elapsed}")
    logger.info(f"Completed: {sum(1 for r in results.values() if r['status'] == 'completed')}")
    logger.info(f"Failed: {sum(1 for r in results.values() if r['status'] == 'failed')}")
    logger.info("=" * 80)
    
    return results


def parse_args():
    """Parse command-line arguments"""
    parser = argparse.ArgumentParser(
        description="Standalone Dukascopy historical data collection (no trading server dependencies)",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Download all pairs, all history
  python backfill_dukascopy_data.py --output-dir data/dukascopy

  # Specific pairs and date range
  python backfill_dukascopy_data.py --pairs EURUSD,GBPUSD --start-date 2020-01-01 --end-date 2024-12-31

  # Resume failed download
  python backfill_dukascopy_data.py --resume
        """
    )
    
    parser.add_argument(
        "--pairs",
        type=str,
        help=f"Comma-separated list of pairs (default: all {len(DEFAULT_PAIRS)} supported pairs)",
    )
    parser.add_argument(
        "--start-date",
        type=str,
        default="2003-01-01",
        help="Start date (YYYY-MM-DD, default: 2003-01-01)",
    )
    parser.add_argument(
        "--end-date",
        type=str,
        default=datetime.now().strftime("%Y-%m-%d"),
        help="End date (YYYY-MM-DD, default: today)",
    )
    parser.add_argument(
        "--output-dir",
        type=str,
        default="data/dukascopy",
        help="Output directory for Parquet files (default: data/dukascopy)",
    )
    parser.add_argument(
        "--batch-size",
        type=int,
        default=3,
        help="Download batch size for rate limiting (default: 3)",
    )
    parser.add_argument(
        "--pause-ms",
        type=int,
        default=5000,
        help="Pause between batches in milliseconds (default: 5000)",
    )
    parser.add_argument(
        "--resume",
        action="store_true",
        help="Resume from last successful checkpoint",
    )
    parser.add_argument(
        "--keep-json",
        action="store_true",
        help="Keep intermediate JSON files (default: delete after conversion)",
    )
    parser.add_argument(
        "--compression",
        type=str,
        default="snappy",
        choices=["snappy", "gzip", "lz4", "zstd"],
        help="Parquet compression algorithm (default: snappy)",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Dry run - validate parameters without downloading",
    )
    parser.add_argument(
        "--verbose",
        action="store_true",
        help="Verbose mode - stream dukascopy-node output in real-time",
    )
    parser.add_argument(
        "--debug",
        action="store_true",
        help="Debug mode - enable debug logging and verbose output",
    )
    
    return parser.parse_args()


def main():
    """Main entry point"""
    # Redirect stdout/stderr to also log to file
    original_stdout = sys.stdout
    original_stderr = sys.stderr
    
    try:
        args = parse_args()
        
        # Update logging level based on flags
        if args.debug:
            logging.getLogger().setLevel(logging.DEBUG)
            logger.setLevel(logging.DEBUG)
        elif args.verbose:
            logging.getLogger().setLevel(logging.INFO)
            logger.setLevel(logging.INFO)
        
        # Create logs directory
        Path("logs").mkdir(exist_ok=True)
        
        # Redirect stdout/stderr to tee logger (captures print statements)
        sys.stdout = TeeLogger(original_stdout, logging.INFO)
        sys.stderr = TeeLogger(original_stderr, logging.ERROR)
        
        logger.info("=" * 80)
        logger.info("Starting Dukascopy data backfill script")
        logger.info(f"Log file: {log_file_path.absolute()}")
        logger.info("=" * 80)
        
        # Parse dates
        try:
            start_date = parse_date(args.start_date)
            end_date = parse_date(args.end_date)
        except ValueError as e:
            logger.error(str(e), exc_info=True)
            return 1
        
        # Validate date range
        if start_date >= end_date:
            logger.error("Start date must be before end date")
            return 1
        
        # Parse pairs
        if args.pairs:
            pairs = [p.strip().upper() for p in args.pairs.split(',')]
        else:
            pairs = DEFAULT_PAIRS
        
        logger.info(f"Selected {len(pairs)} pairs: {', '.join(pairs)}")
        
        # Check prerequisites
        if not args.dry_run:
            logger.info("Checking dukascopy-node CLI...")
            if not check_dukascopy_cli():
                logger.error("dukascopy-node CLI not found")
                logger.error("Install with: npm install -g dukascopy-node")
                logger.error("Or locally: npm install dukascopy-node")
                return 1
        
        # Setup directories
        output_dir = Path(args.output_dir)
        output_dir.mkdir(parents=True, exist_ok=True)
        
        if args.dry_run:
            logger.info("DRY RUN - Would process:")
            for symbol in pairs:
                logger.info(f"  - {symbol}")
            logger.info(f"Output directory: {output_dir}")
            logger.info(f"Date range: {start_date.date()} to {end_date.date()}")
            return 0
    
        # Run backfill
        try:
            verbose = args.verbose or args.debug
            results = backfill_multiple_symbols(
                pairs,
                start_date,
                end_date,
                output_dir,
                args.batch_size,
                args.pause_ms,
                args.compression,
                args.keep_json,
                args.resume,
                verbose
            )
            
            # Check if any failed
            failed_count = sum(1 for r in results.values() if r['status'] == 'failed')
            if failed_count > 0:
                logger.warning(f"{failed_count} symbols failed")
                return 1
            
            logger.info("[SUCCESS] All symbols completed successfully")
            return 0
        
        except KeyboardInterrupt:
            logger.warning("Interrupted by user", exc_info=True)
            return 130
        except Exception as e:
            logger.error(f"Backfill failed: {e}", exc_info=True)
            import traceback
            logger.error(f"Full traceback:\n{traceback.format_exc()}")
            return 1
    except Exception as e:
        # Catch any errors that occur before logging is fully set up
        import traceback
        error_msg = f"Fatal error before logging setup: {e}\n{traceback.format_exc()}"
        # Try to log to file directly
        try:
            with open(log_file_path, 'a', encoding='utf-8') as f:
                f.write(f"\n{datetime.now().isoformat()} - FATAL - {error_msg}\n")
        except:
            pass
        # Also print to stderr
        print(error_msg, file=original_stderr)
        return 1
    finally:
        # Always restore original stdout/stderr
        sys.stdout = original_stdout
        sys.stderr = original_stderr


if __name__ == "__main__":
    exit(main())
