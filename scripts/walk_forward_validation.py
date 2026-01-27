#!/usr/bin/env python
"""
Walk-Forward Validation

Implements walk-forward validation with expanding/rolling windows to prevent
temporal leakage and overfitting to specific time periods.

Reference: Prado (2018) - Advances in Financial Machine Learning, Ch. 12
"""

import sys
import os
from typing import Dict, Any, List, Callable, Optional
from datetime import datetime, timedelta
import pandas as pd
import numpy as np

# Add source to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '../src/backend/trading_server/src'))


def walk_forward_validation(
    data: pd.DataFrame,
    train_window_days: int = 180,
    test_window_days: int = 30,
    step_days: int = 30,
    window_type: str = "expanding",  # "expanding" or "rolling"
    backtest_func: Optional[Callable] = None,
    **backtest_kwargs
) -> Dict[str, Any]:
    """
    Walk-forward validation with expanding/rolling windows.
    
    This function splits data into multiple train/test windows, ensuring
    that training data always comes before test data (no future data leakage).
    
    Args:
        data: DataFrame with 'timestamp' column and price data (bid, ask, etc.)
        train_window_days: Training window size in days
        test_window_days: Test window size in days
        step_days: Step size between windows in days
        window_type: "expanding" (train window grows) or "rolling" (fixed size)
        backtest_func: Function to run backtest on train/test data.
                       Should accept (train_data, test_data, **kwargs) and return metrics dict
        **backtest_kwargs: Additional arguments for backtest function
    
    Returns:
        Dictionary with:
            - results: List of metrics for each window
            - aggregated_metrics: Aggregated statistics across windows
            - window_info: Information about each window (dates, sizes)
    """
    # Validate inputs
    if 'timestamp' not in data.columns:
        raise ValueError("Data must contain 'timestamp' column")
    
    if window_type not in ["expanding", "rolling"]:
        raise ValueError(f"window_type must be 'expanding' or 'rolling', got '{window_type}'")
    
    if train_window_days <= 0 or test_window_days <= 0 or step_days <= 0:
        raise ValueError("Window sizes and step size must be positive")
    
    # Ensure timestamp is datetime
    data = data.copy()
    if not pd.api.types.is_datetime64_any_dtype(data['timestamp']):
        data['timestamp'] = pd.to_datetime(data['timestamp'])
    
    # Sort by timestamp to ensure temporal ordering
    data = data.sort_values('timestamp').reset_index(drop=True)
    
    # Get date range
    start_date = data['timestamp'].min()
    end_date = data['timestamp'].max()
    
    # Calculate minimum required data
    min_required_days = train_window_days + test_window_days
    total_days = (end_date - start_date).days
    
    if total_days < min_required_days:
        raise ValueError(
            f"Insufficient data: need at least {min_required_days} days, "
            f"got {total_days} days"
        )
    
    # Initialize results
    results = []
    window_info = []
    
    # Track initial train start for expanding windows
    initial_train_start = start_date
    
    # Current test window start
    current_test_start = start_date + timedelta(days=train_window_days)
    
    window_idx = 0
    
    # Generate windows
    while current_test_start + timedelta(days=test_window_days) <= end_date:
        # Determine train window
        if window_type == "expanding":
            # Expanding: train from initial start to test start
            train_start = initial_train_start
            train_end = current_test_start
        else:  # rolling
            # Rolling: train from (test_start - train_window_days) to test_start
            train_start = current_test_start - timedelta(days=train_window_days)
            train_end = current_test_start
        
        test_end = current_test_start + timedelta(days=test_window_days)
        
        # Extract train and test data
        train_mask = (data['timestamp'] >= train_start) & (data['timestamp'] < train_end)
        test_mask = (data['timestamp'] >= current_test_start) & (data['timestamp'] < test_end)
        
        train_data = data[train_mask].copy()
        test_data = data[test_mask].copy()
        
        # Validate no temporal leakage
        if len(train_data) > 0 and len(test_data) > 0:
            max_train_time = train_data['timestamp'].max()
            min_test_time = test_data['timestamp'].min()
            
            if max_train_time >= min_test_time:
                raise ValueError(
                    f"Temporal leakage detected in window {window_idx}: "
                    f"max train time {max_train_time} >= min test time {min_test_time}"
                )
        
        # Check if we have sufficient data
        if len(train_data) == 0:
            print(f"Warning: Window {window_idx} has no training data, skipping")
            current_test_start += timedelta(days=step_days)
            window_idx += 1
            continue
        
        if len(test_data) == 0:
            print(f"Warning: Window {window_idx} has no test data, skipping")
            current_test_start += timedelta(days=step_days)
            window_idx += 1
            continue
        
        # Run backtest if function provided
        window_metrics = {}
        if backtest_func is not None:
            try:
                window_metrics = backtest_func(
                    train_data=train_data,
                    test_data=test_data,
                    **backtest_kwargs
                )
            except Exception as e:
                print(f"Error in window {window_idx}: {e}")
                window_metrics = {"error": str(e)}
        else:
            # Default: just return window statistics
            window_metrics = {
                "train_rows": len(train_data),
                "test_rows": len(test_data),
                "train_days": (train_end - train_start).days,
                "test_days": (test_end - current_test_start).days,
            }
        
        # Store window information
        window_info.append({
            "window_idx": window_idx,
            "train_start": train_start.isoformat() if isinstance(train_start, datetime) else str(train_start),
            "train_end": train_end.isoformat() if isinstance(train_end, datetime) else str(train_end),
            "test_start": current_test_start.isoformat() if isinstance(current_test_start, datetime) else str(current_test_start),
            "test_end": test_end.isoformat() if isinstance(test_end, datetime) else str(test_end),
            "train_rows": len(train_data),
            "test_rows": len(test_data),
        })
        
        # Add window info to metrics
        window_metrics["window_idx"] = window_idx
        window_metrics["train_start"] = train_start.isoformat() if isinstance(train_start, datetime) else str(train_start)
        window_metrics["test_start"] = current_test_start.isoformat() if isinstance(current_test_start, datetime) else str(current_test_start)
        
        results.append(window_metrics)
        
        # Move to next window
        current_test_start += timedelta(days=step_days)
        window_idx += 1
    
    if len(results) == 0:
        raise ValueError("No valid windows generated. Check data range and window sizes.")
    
    # Aggregate metrics across windows
    aggregated_metrics = _aggregate_results(results)
    
    return {
        "results": results,
        "aggregated_metrics": aggregated_metrics,
        "window_info": window_info,
        "config": {
            "train_window_days": train_window_days,
            "test_window_days": test_window_days,
            "step_days": step_days,
            "window_type": window_type,
            "total_windows": len(results),
            "data_start": start_date.isoformat() if isinstance(start_date, datetime) else str(start_date),
            "data_end": end_date.isoformat() if isinstance(end_date, datetime) else str(end_date),
        }
    }


def _aggregate_results(results: List[Dict[str, Any]]) -> Dict[str, Any]:
    """
    Aggregate metrics across all windows.
    
    Args:
        results: List of metric dictionaries from each window
    
    Returns:
        Dictionary with aggregated statistics
    """
    if not results:
        return {}
    
    # Collect all metric keys (excluding window metadata)
    exclude_keys = {"window_idx", "train_start", "test_start", "error"}
    metric_keys = set()
    for r in results:
        metric_keys.update(k for k in r.keys() if k not in exclude_keys)
    
    aggregated = {}
    
    for key in metric_keys:
        values = [r[key] for r in results if key in r and not isinstance(r[key], str)]
        
        if not values:
            continue
        
        # Filter out None and non-numeric values
        numeric_values = [v for v in values if v is not None and isinstance(v, (int, float, np.number))]
        
        if not numeric_values:
            continue
        
        aggregated[f"{key}_mean"] = float(np.mean(numeric_values))
        aggregated[f"{key}_std"] = float(np.std(numeric_values))
        aggregated[f"{key}_min"] = float(np.min(numeric_values))
        aggregated[f"{key}_max"] = float(np.max(numeric_values))
        aggregated[f"{key}_median"] = float(np.median(numeric_values))
    
    # Add summary statistics
    aggregated["num_windows"] = len(results)
    aggregated["successful_windows"] = len([r for r in results if "error" not in r])
    
    return aggregated


if __name__ == "__main__":
    # Example usage
    print("Walk-Forward Validation Module")
    print("Import this module to use walk_forward_validation() function")
