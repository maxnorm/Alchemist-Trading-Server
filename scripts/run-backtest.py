#!/usr/bin/env python
"""
Backtest Runner CLI

Run backtests on historical data with trained models.

Usage:
    python scripts/run-backtest.py --data data/ticks.parquet --model models/dqn_v1 --output results/
    python scripts/run-backtest.py --data data/ticks.parquet --model models/dqn_v1 --output results/ --slippage volume --seed 42
"""

import argparse
import os
import sys
import json
from datetime import datetime
from pathlib import Path

# Add source to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '../src/backend/trading_server/src'))
sys.path.insert(0, os.path.join(os.path.dirname(__file__)))

import numpy as np

try:
    import pandas as pd
except ImportError:
    print("pandas required. Install with: pip install pandas")
    sys.exit(1)

try:
    from walk_forward_validation import walk_forward_validation
    WALK_FORWARD_AVAILABLE = True
except ImportError:
    WALK_FORWARD_AVAILABLE = False
    print("Warning: walk_forward_validation module not available")


def load_data(data_path: str) -> pd.DataFrame:
    """Load and validate backtest data"""
    path = Path(data_path)
    
    if not path.exists():
        raise FileNotFoundError(f"Data file not found: {data_path}")
    
    if path.suffix == '.parquet':
        data = pd.read_parquet(path)
    elif path.suffix == '.csv':
        data = pd.read_csv(path)
    else:
        raise ValueError(f"Unsupported file format: {path.suffix}")
    
    # Validate required columns
    required = ['bid', 'ask']
    missing = [c for c in required if c not in data.columns]
    if missing:
        raise ValueError(f"Missing required columns: {missing}")
    
    print(f"Loaded {len(data)} rows from {data_path}")
    print(f"Columns: {list(data.columns)}")
    
    if 'timestamp' in data.columns:
        print(f"Date range: {data['timestamp'].min()} to {data['timestamp'].max()}")
    
    return data


def load_agent(model_path: str, state_shape: tuple, action_size: int):
    """Load trained agent"""
    try:
        from agents.dqn_agent import DQNAgent
        
        agent = DQNAgent(
            state_shape=state_shape,
            action_size=action_size
        )
        
        # Try to load model
        if Path(model_path).exists():
            agent.load(model_path)
            print(f"Loaded model from {model_path}")
        else:
            print(f"Warning: Model path not found: {model_path}")
            print("Using untrained agent for demonstration")
        
        return agent
    except ImportError as e:
        print(f"Could not import agent: {e}")
        return None


def create_slippage_model(slippage_type: str, transaction_cost: float):
    """Create slippage model based on type"""
    from environments.slippage_models import (
        FixedSlippage,
        VolumeBasedSlippage,
        RandomSlippage,
        NoSlippage
    )
    
    models = {
        'none': lambda: NoSlippage(),
        'fixed': lambda: FixedSlippage(slippage_pct=transaction_cost),
        'volume': lambda: VolumeBasedSlippage(impact_coefficient=0.1),
        'random': lambda: RandomSlippage(min_pct=0, max_pct=transaction_cost * 2),
    }
    
    if slippage_type not in models:
        raise ValueError(f"Unknown slippage type: {slippage_type}. Available: {list(models.keys())}")
    
    return models[slippage_type]()


def run_backtest(
    data: pd.DataFrame,
    agent,
    output_dir: str,
    slippage_type: str = 'fixed',
    transaction_cost: float = 0.0001,
    initial_balance: float = 10000.0,
    window_size: int = 50,
    seed: int = 42
) -> dict:
    """
    Run backtest with given agent and data.
    
    Returns:
        Dictionary of results
    """
    from environments.historical_env import HistoricalTradingEnv
    
    # Create slippage model
    slippage = create_slippage_model(slippage_type, transaction_cost)
    print(f"Using slippage model: {slippage.get_description()}")
    
    # Create environment
    env = HistoricalTradingEnv(
        data=data,
        window_size=window_size,
        initial_balance=initial_balance,
        transaction_cost=transaction_cost,
        slippage_model=slippage,
        seed=seed
    )
    
    print(f"\nStarting backtest...")
    print(f"  Initial balance: ${initial_balance:,.2f}")
    print(f"  Transaction cost: {transaction_cost:.4%}")
    print(f"  Window size: {window_size}")
    print(f"  Seed: {seed}")
    print(f"  Data points: {len(data)}")
    
    # Run backtest
    state, info = env.reset(seed=seed)
    done = False
    step = 0
    
    equity_curve = [initial_balance]
    actions_taken = []
    
    start_time = datetime.now()
    
    while not done:
        # Get action from agent
        if agent is not None:
            action = agent.act(state, training=False)
        else:
            # Random agent for testing
            action = np.random.randint(0, env.action_space.n)
        
        # Take step
        state, reward, done, truncated, info = env.step(action)
        
        equity_curve.append(info['equity'])
        actions_taken.append(action)
        
        step += 1
        
        # Progress reporting
        if step % 1000 == 0:
            pct_complete = min(100, (step / (len(data) - window_size)) * 100)
            print(f"  Step {step}: Equity ${info['equity']:,.2f} ({pct_complete:.1f}% complete)")
    
    elapsed = (datetime.now() - start_time).total_seconds()
    print(f"\nBacktest complete in {elapsed:.2f} seconds")
    
    # Get metrics
    metrics = env.get_performance_metrics()
    trade_history = env.get_trade_history()
    
    # Build results
    results = {
        'run_info': {
            'seed': seed,
            'data_path': str(data.columns.tolist()),
            'data_rows': len(data),
            'initial_balance': initial_balance,
            'transaction_cost': transaction_cost,
            'slippage_type': slippage_type,
            'window_size': window_size,
            'run_date': datetime.now().isoformat(),
            'elapsed_seconds': elapsed
        },
        'metrics': metrics,
        'summary': {
            'final_balance': metrics['final_balance'],
            'total_return': metrics['total_return'],
            'total_trades': metrics['total_trades'],
            'win_rate': metrics['win_rate'],
            'sharpe_ratio': metrics['sharpe_ratio'],
            'max_drawdown': metrics['max_drawdown'],
            'profit_factor': metrics['profit_factor']
        }
    }
    
    # Save results
    output_path = Path(output_dir)
    output_path.mkdir(parents=True, exist_ok=True)
    
    # Save summary
    with open(output_path / 'results.json', 'w') as f:
        json.dump(results, f, indent=2, default=str)
    
    # Save equity curve
    pd.DataFrame({'equity': equity_curve}).to_csv(
        output_path / 'equity_curve.csv',
        index=False
    )
    
    # Save trade history
    if trade_history:
        pd.DataFrame(trade_history).to_csv(
            output_path / 'trades.csv',
            index=False
        )
    
    # Save action distribution
    action_counts = pd.Series(actions_taken).value_counts().to_dict()
    with open(output_path / 'action_distribution.json', 'w') as f:
        json.dump(action_counts, f, indent=2)
    
    print(f"\nResults saved to {output_path}")
    
    return results


def print_results(results: dict):
    """Print formatted results"""
    summary = results['summary']
    
    print("\n" + "=" * 60)
    print("BACKTEST RESULTS")
    print("=" * 60)
    print(f"  Final Balance:   ${summary['final_balance']:,.2f}")
    print(f"  Total Return:    {summary['total_return']:.2%}")
    print(f"  Total Trades:    {summary['total_trades']}")
    print(f"  Win Rate:        {summary['win_rate']:.2%}")
    print(f"  Sharpe Ratio:    {summary['sharpe_ratio']:.2f}")
    print(f"  Max Drawdown:    {summary['max_drawdown']:.2%}")
    print(f"  Profit Factor:   {summary['profit_factor']:.2f}")
    print("=" * 60)


def calculate_max_drawdown(equity_curve: list) -> float:
    """Calculate maximum drawdown from equity curve"""
    peak = equity_curve[0]
    max_dd = 0
    
    for equity in equity_curve:
        if equity > peak:
            peak = equity
        dd = (peak - equity) / peak if peak > 0 else 0
        if dd > max_dd:
            max_dd = dd
    
    return max_dd


def calculate_sharpe(equity_curve: list, risk_free_rate: float = 0.02) -> float:
    """Calculate Sharpe ratio from equity curve"""
    if len(equity_curve) < 2:
        return 0.0
    
    returns = np.diff(equity_curve) / equity_curve[:-1]
    
    if np.std(returns) == 0:
        return 0.0
    
    excess_returns = np.mean(returns) - risk_free_rate / 252
    return excess_returns / np.std(returns) * np.sqrt(252)


def main():
    parser = argparse.ArgumentParser(
        description="Run backtest on historical data",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
    # Basic backtest
    python scripts/run-backtest.py --data data/ticks.parquet --model models/v1 --output results/
    
    # With specific slippage model
    python scripts/run-backtest.py --data data/ticks.parquet --model models/v1 --output results/ --slippage volume
    
    # With custom parameters
    python scripts/run-backtest.py --data data/ticks.parquet --model models/v1 --output results/ \\
        --balance 50000 --cost 0.0002 --window 100 --seed 123
        """
    )
    
    parser.add_argument(
        "--data",
        required=True,
        help="Path to data file (parquet or csv)"
    )
    parser.add_argument(
        "--model",
        required=True,
        help="Path to trained model directory"
    )
    parser.add_argument(
        "--output",
        required=True,
        help="Output directory for results"
    )
    parser.add_argument(
        "--slippage",
        default="fixed",
        choices=["none", "fixed", "volume", "random"],
        help="Slippage model type (default: fixed)"
    )
    parser.add_argument(
        "--cost",
        type=float,
        default=0.0001,
        help="Transaction cost as fraction (default: 0.0001 = 1 pip)"
    )
    parser.add_argument(
        "--balance",
        type=float,
        default=10000.0,
        help="Initial balance (default: 10000)"
    )
    parser.add_argument(
        "--window",
        type=int,
        default=50,
        help="Observation window size (default: 50)"
    )
    parser.add_argument(
        "--seed",
        type=int,
        default=42,
        help="Random seed for reproducibility (default: 42)"
    )
    parser.add_argument(
        "--walk-forward",
        action="store_true",
        help="Enable walk-forward validation mode"
    )
    parser.add_argument(
        "--train-window",
        type=int,
        default=180,
        help="Training window size in days for walk-forward (default: 180)"
    )
    parser.add_argument(
        "--test-window",
        type=int,
        default=30,
        help="Test window size in days for walk-forward (default: 30)"
    )
    parser.add_argument(
        "--step-size",
        type=int,
        default=30,
        help="Step size in days for walk-forward (default: 30)"
    )
    parser.add_argument(
        "--window-type",
        type=str,
        default="expanding",
        choices=["expanding", "rolling"],
        help="Window type for walk-forward: expanding (grows) or rolling (fixed) (default: expanding)"
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Show configuration without running"
    )
    
    args = parser.parse_args()
    
    print("\n" + "=" * 60)
    print("BACKTEST CONFIGURATION")
    print("=" * 60)
    print(f"  Data:          {args.data}")
    print(f"  Model:         {args.model}")
    print(f"  Output:        {args.output}")
    print(f"  Slippage:      {args.slippage}")
    print(f"  Cost:          {args.cost:.4%}")
    print(f"  Balance:       ${args.balance:,.2f}")
    print(f"  Window:        {args.window}")
    print(f"  Seed:          {args.seed}")
    if args.walk_forward:
        print(f"  Walk-Forward:  Enabled")
        print(f"  Train Window:  {args.train_window} days")
        print(f"  Test Window:   {args.test_window} days")
        print(f"  Step Size:     {args.step_size} days")
        print(f"  Window Type:   {args.window_type}")
    print("=" * 60)
    
    if args.dry_run:
        print("\nDry run - exiting without execution")
        return
    
    # Load data
    print("\nLoading data...")
    data = load_data(args.data)
    
    # Determine state shape from data
    n_features = 4 + len([c for c in data.columns if c not in ['timestamp', 'bid', 'ask', 'volume', 'symbol']])
    state_shape = (args.window, n_features)
    action_size = 4  # HOLD, BUY, SELL, CLOSE
    
    # Load agent
    print("\nLoading agent...")
    agent = load_agent(args.model, state_shape, action_size)
    
    # Run backtest with or without walk-forward
    if args.walk_forward:
        if not WALK_FORWARD_AVAILABLE:
            print("Error: Walk-forward validation not available")
            sys.exit(1)
        
        if 'timestamp' not in data.columns:
            print("Error: Walk-forward validation requires 'timestamp' column in data")
            sys.exit(1)
        
        print("\nRunning walk-forward validation...")
        
        # Define backtest function for walk-forward
        def backtest_func(train_data, test_data, **kwargs):
            """Run backtest on train/test split"""
            # For walk-forward, we typically train on train_data and test on test_data
            # For simplicity, we'll just run backtest on test_data
            # In a full implementation, you would train the model on train_data first
            return run_backtest(
                data=test_data,
                agent=agent,
                output_dir=None,  # Don't save individual window results
                slippage_type=args.slippage,
                transaction_cost=args.cost,
                initial_balance=args.balance,
                window_size=args.window,
                seed=args.seed
            )['metrics']
        
        # Run walk-forward validation
        wf_results = walk_forward_validation(
            data=data,
            train_window_days=args.train_window,
            test_window_days=args.test_window,
            step_days=args.step_size,
            window_type=args.window_type,
            backtest_func=backtest_func
        )
        
        # Save walk-forward results
        output_path = Path(args.output)
        output_path.mkdir(parents=True, exist_ok=True)
        
        with open(output_path / 'walk_forward_results.json', 'w') as f:
            json.dump(wf_results, f, indent=2, default=str)
        
        # Print summary
        print("\n" + "=" * 60)
        print("WALK-FORWARD VALIDATION RESULTS")
        print("=" * 60)
        print(f"  Total Windows: {wf_results['config']['total_windows']}")
        print(f"  Window Type:    {wf_results['config']['window_type']}")
        
        agg = wf_results['aggregated_metrics']
        if 'sharpe_ratio_mean' in agg:
            print(f"\n  Sharpe Ratio:")
            print(f"    Mean:   {agg['sharpe_ratio_mean']:.3f}")
            print(f"    Std:    {agg['sharpe_ratio_std']:.3f}")
            print(f"    Min:    {agg['sharpe_ratio_min']:.3f}")
            print(f"    Max:    {agg['sharpe_ratio_max']:.3f}")
        
        if 'total_return_mean' in agg:
            print(f"\n  Total Return:")
            print(f"    Mean:   {agg['total_return_mean']:.2%}")
            print(f"    Std:    {agg['total_return_std']:.2%}")
            print(f"    Min:    {agg['total_return_min']:.2%}")
            print(f"    Max:    {agg['total_return_max']:.2%}")
        
        print("=" * 60)
        print(f"\nResults saved to {output_path / 'walk_forward_results.json'}")
        
        results = wf_results
    else:
        # Run standard backtest
        results = run_backtest(
            data=data,
            agent=agent,
            output_dir=args.output,
            slippage_type=args.slippage,
            transaction_cost=args.cost,
            initial_balance=args.balance,
            window_size=args.window,
            seed=args.seed
        )
        
        # Print results
        print_results(results)


if __name__ == "__main__":
    main()
