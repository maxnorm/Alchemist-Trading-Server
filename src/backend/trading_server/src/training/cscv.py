"""
Combinatorially Symmetric Cross-Validation (CSCV)

Implementation of the CSCV algorithm for estimating Probability of Backtest Overfitting (PBO)
as described in:

Bailey, D. H., Borwein, J. M., López de Prado, M., & Zhu, Q. J. (2014).
"The Probability of Backtest Overfitting." Journal of Computational Finance, 17(4).

This module provides functions to:
- Partition data into symmetric train/test splits
- Evaluate multiple strategy configurations
- Calculate PBO and performance degradation metrics
"""

import numpy as np
import pandas as pd
from typing import Dict, Any, List, Callable, Optional, Tuple
from itertools import combinations
import logging

logger = logging.getLogger(__name__)


def combinatorially_symmetric_cross_validation(
    data: pd.DataFrame,
    strategy_configs: List[Dict[str, Any]],
    n_splits: int = 4,
    evaluation_metric: str = "sharpe_ratio",
    train_func: Optional[Callable] = None,
    evaluate_func: Optional[Callable] = None,
) -> Dict[str, Any]:
    """
    Estimate Probability of Backtest Overfitting (PBO) using CSCV.

    The CSCV algorithm:
    1. Partitions data into n_splits equal parts
    2. For each combination of train/test splits:
       - Trains all strategies on training partition
       - Evaluates all strategies on test partition
       - Ranks strategies by performance
    3. Calculates PBO using combinatorial analysis
    4. Calculates performance degradation ratio

    Args:
        data: Historical data with timestamp column (must be sorted by timestamp)
        strategy_configs: List of strategy configurations to test.
                         Each config should be a dict with strategy parameters.
                         Minimum 10 strategies recommended for reliable PBO.
        n_splits: Number of partitions for CSCV (typically 4)
        evaluation_metric: Metric to use for ranking strategies.
                          Options: "sharpe_ratio", "total_return", "profit_factor", etc.
        train_func: Function to train a strategy on data.
                   Signature: train_func(data, config) -> trained_model
        evaluate_func: Function to evaluate a strategy on data.
                      Signature: evaluate_func(data, model, config) -> metrics_dict

    Returns:
        Dictionary with:
            - pbo: Probability of backtest overfitting (0-1)
            - performance_degradation: Expected performance drop (0-1)
            - logit_pbo: Logit of PBO
            - strategy_rankings: Rankings for each split combination
            - n_strategies: Number of strategies tested
            - n_splits: Number of splits used
    """
    # Validate inputs
    if len(strategy_configs) < 2:
        raise ValueError(
            f"Need at least 2 strategy configurations, got {len(strategy_configs)}"
        )

    if len(strategy_configs) < 10:
        logger.warning(
            f"Only {len(strategy_configs)} strategies provided. "
            "PBO estimation is more reliable with ≥10 strategies."
        )

    if n_splits < 2:
        raise ValueError(f"n_splits must be at least 2, got {n_splits}")

    if "timestamp" not in data.columns:
        raise ValueError("Data must contain 'timestamp' column")

    # Ensure data is sorted by timestamp
    data = data.copy()
    if not pd.api.types.is_datetime64_any_dtype(data["timestamp"]):
        data["timestamp"] = pd.to_datetime(data["timestamp"])
    data = data.sort_values("timestamp").reset_index(drop=True)

    # Partition data into n_splits equal parts
    partitions = _partition_data(data, n_splits)

    # Generate all combinations of train/test splits
    # For n_splits=4, we get C(4,2) = 6 combinations
    # split_combinations = list(combinations(range(n_splits), n_splits // 2))

    # For each combination, evaluate strategies
    all_rankings = []
    all_performances = []

    for train_indices, test_indices in _generate_train_test_splits(n_splits):
        # Combine partitions for train and test
        train_data = pd.concat(
            [partitions[i] for i in train_indices], ignore_index=True
        )
        train_data = train_data.sort_values("timestamp").reset_index(drop=True)

        test_data = pd.concat([partitions[i] for i in test_indices], ignore_index=True)
        test_data = test_data.sort_values("timestamp").reset_index(drop=True)

        # Evaluate all strategies on this split
        strategy_performances = []

        for config_idx, config in enumerate(strategy_configs):
            try:
                if train_func is not None and evaluate_func is not None:
                    # Train and evaluate
                    model = train_func(train_data, config)
                    metrics = evaluate_func(test_data, model, config)
                else:
                    # Use default evaluation (just return config-based metrics)
                    metrics = _default_evaluate(strategy_configs, config_idx, test_data)

                # Extract evaluation metric
                if evaluation_metric not in metrics:
                    logger.warning(
                        f"Metric '{evaluation_metric}' not found in metrics. "
                        f"Available: {list(metrics.keys())}"
                    )
                    # Try to use first available metric
                    if metrics:
                        evaluation_metric = list(metrics.keys())[0]
                    else:
                        performance = 0.0
                        strategy_performances.append((config_idx, performance))
                        continue

                performance = metrics.get(evaluation_metric, 0.0)
                strategy_performances.append((config_idx, performance))

            except Exception as e:
                logger.error(f"Error evaluating strategy {config_idx}: {e}")
                strategy_performances.append((config_idx, -np.inf))

        # Rank strategies by performance (descending)
        strategy_performances.sort(key=lambda x: x[1], reverse=True)
        rankings = [idx for idx, _ in strategy_performances]
        performances = [perf for _, perf in strategy_performances]

        all_rankings.append(rankings)
        all_performances.append(performances)

    # Calculate PBO
    pbo, logit_pbo = _calculate_pbo(all_rankings, len(strategy_configs))

    # Calculate performance degradation
    performance_degradation = _calculate_performance_degradation(
        all_performances, all_rankings
    )

    return {
        "pbo": float(pbo),
        "performance_degradation": float(performance_degradation),
        "logit_pbo": float(logit_pbo),
        "strategy_rankings": all_rankings,
        "strategy_performances": all_performances,
        "n_strategies": len(strategy_configs),
        "n_splits": n_splits,
        "evaluation_metric": evaluation_metric,
    }


def _partition_data(data: pd.DataFrame, n_splits: int) -> List[pd.DataFrame]:
    """
    Partition data into n_splits equal parts.

    Args:
        data: DataFrame sorted by timestamp
        n_splits: Number of partitions

    Returns:
        List of DataFrames, one per partition
    """
    n_rows = len(data)
    partition_size = n_rows // n_splits

    partitions = []
    for i in range(n_splits):
        start_idx = i * partition_size
        if i == n_splits - 1:
            # Last partition gets remaining rows
            end_idx = n_rows
        else:
            end_idx = (i + 1) * partition_size

        partitions.append(data.iloc[start_idx:end_idx].copy())

    return partitions


def _generate_train_test_splits(n_splits: int) -> List[Tuple[List[int], List[int]]]:
    """
    Generate all symmetric train/test split combinations.

    For n_splits=4, generates:
    - Train: [0,1], Test: [2,3]
    - Train: [0,2], Test: [1,3]
    - Train: [0,3], Test: [1,2]
    - Train: [1,2], Test: [0,3]
    - Train: [1,3], Test: [0,2]
    - Train: [2,3], Test: [0,1]

    Args:
        n_splits: Number of partitions

    Returns:
        List of (train_indices, test_indices) tuples
    """
    all_indices = list(range(n_splits))
    train_size = n_splits // 2

    # Generate all combinations of train indices
    train_combinations = list(combinations(all_indices, train_size))

    splits = []
    for train_indices in train_combinations:
        test_indices = [i for i in all_indices if i not in train_indices]
        splits.append((list(train_indices), test_indices))

    return splits


def _calculate_pbo(
    all_rankings: List[List[int]], n_strategies: int
) -> Tuple[float, float]:
    """
    Calculate Probability of Backtest Overfitting (PBO).

    PBO is calculated as the probability that the best strategy in-sample
    is not the best strategy out-of-sample.

    Args:
        all_rankings: List of strategy rankings for each split
                     Each ranking is a list of strategy indices ordered by performance
        n_strategies: Total number of strategies

    Returns:
        Tuple of (pbo, logit_pbo)
    """
    if not all_rankings:
        return 0.0, 0.0

    # For each split, check if best strategy (rank 0) maintains good performance
    # across other splits
    best_strategy_consistency = []

    for split_idx, rankings in enumerate(all_rankings):
        if not rankings:
            continue

        # Best strategy in this split
        best_strategy = rankings[0]

        # Check its rank in other splits
        ranks_in_other_splits = []
        for other_idx, other_rankings in enumerate(all_rankings):
            if other_idx == split_idx:
                continue
            if best_strategy in other_rankings:
                rank = other_rankings.index(best_strategy)
                ranks_in_other_splits.append(rank)

        if ranks_in_other_splits:
            # Calculate average rank in other splits
            avg_rank = float(np.mean(ranks_in_other_splits))
            # Normalize to [0, 1] where 0 = best, 1 = worst
            normalized_rank = avg_rank / (n_strategies - 1) if n_strategies > 1 else 0.0
            best_strategy_consistency.append(normalized_rank)

    if not best_strategy_consistency:
        return 0.0, 0.0

    # PBO is the proportion of cases where best strategy performs poorly out-of-sample
    # Higher normalized rank = worse performance = higher overfitting risk
    pbo = float(np.mean(best_strategy_consistency))

    # Calculate logit of PBO
    if pbo <= 0:
        logit_pbo = -np.inf
    elif pbo >= 1:
        logit_pbo = np.inf
    else:
        logit_pbo = np.log(pbo / (1 - pbo))

    return float(pbo), float(logit_pbo)


def _calculate_performance_degradation(
    all_performances: List[List[float]], all_rankings: List[List[int]]
) -> float:
    """
    Calculate expected performance degradation.

    Measures how much performance degrades when moving from in-sample to out-of-sample.

    Args:
        all_performances: List of performance lists for each split
        all_rankings: List of strategy rankings for each split

    Returns:
        Performance degradation ratio (0-1, higher = more degradation)
    """
    if not all_performances or not all_rankings:
        return 0.0

    degradations = []

    for split_idx, (performances, rankings) in enumerate(
        zip(all_performances, all_rankings)
    ):
        if not performances or not rankings:
            continue

        # Best strategy performance in this split (in-sample)
        best_performance = performances[rankings[0]]

        # Average performance of best strategy in other splits (out-of-sample)
        best_strategy = rankings[0]
        out_of_sample_performances = []

        for other_idx, (other_performances, other_rankings) in enumerate(
            zip(all_performances, all_rankings)
        ):
            if other_idx == split_idx:
                continue
            if best_strategy in other_rankings:
                strategy_idx = other_rankings.index(best_strategy)
                out_of_sample_performances.append(other_performances[strategy_idx])

        if out_of_sample_performances and best_performance != 0:
            avg_out_of_sample = float(np.mean(out_of_sample_performances))
            degradation = 1 - (avg_out_of_sample / best_performance)
            degradations.append(max(0.0, min(1.0, degradation)))  # Clamp to [0, 1]

    if not degradations:
        return 0.0

    return float(np.mean(degradations))


def _default_evaluate(
    strategy_configs: List[Dict[str, Any]], config_idx: int, test_data: pd.DataFrame
) -> Dict[str, float]:
    """
    Default evaluation function when train/evaluate functions not provided.

    This is a placeholder that returns dummy metrics. In practice, you should
    provide proper train_func and evaluate_func.

    Args:
        strategy_configs: List of all strategy configs
        config_idx: Index of current strategy config
        test_data: Test data

    Returns:
        Dictionary of metrics
    """
    # This is a placeholder - in real usage, you should provide proper functions
    logger.warning(
        "Using default evaluation function. Provide train_func and evaluate_func for proper evaluation."
    )

    # Return dummy metrics based on config index
    return {
        "sharpe_ratio": np.random.randn() * 0.5 + 1.0,
        "total_return": np.random.randn() * 0.1,
        "profit_factor": np.random.rand() * 2.0 + 0.5,
    }


def interpret_pbo(pbo: float) -> str:
    """
    Interpret PBO value and provide risk assessment.

    Args:
        pbo: Probability of backtest overfitting (0-1)

    Returns:
        Interpretation string
    """
    if pbo < 0.05:
        return "Low overfitting risk (PBO < 0.05)"
    elif pbo < 0.10:
        return "Moderate overfitting risk (0.05 ≤ PBO < 0.10)"
    else:
        return "High overfitting risk (PBO ≥ 0.10) - strategy likely overfitted"
