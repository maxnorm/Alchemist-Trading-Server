"""
Historical Backfill DAG
On-demand backfill of historical MT5 data with OHLCV aggregation
"""

from datetime import timedelta
from airflow import DAG
from airflow.operators.python import PythonOperator
from airflow.utils.dates import days_ago
import os
import sys

# Default arguments
default_args = {
    "owner": "data_team",
    "depends_on_past": False,
    "email_on_failure": False,
    "email_on_retry": False,
    "retries": 3,
    "retry_delay": timedelta(minutes=5),
}

# DAG definition
dag = DAG(
    "historical_backfill",
    default_args=default_args,
    description="Historical data backfill from MT5 with OHLCV aggregation",
    schedule_interval=None,  # Manual trigger only
    start_date=days_ago(1),
    catchup=False,
    max_active_runs=1,
    tags=["backfill", "historical", "mt5"],
)


def backfill_ticks_task(**context):
    """
    Task to backfill ticks from MT5
    Reads configuration from Airflow variables or context
    """
    import subprocess
    from airflow.models import Variable

    # Get configuration from Airflow variables or context
    symbol = Variable.get("backfill_symbol", default_var="EURUSD")
    start_time = Variable.get("backfill_start_time", default_var=None)
    end_time = Variable.get("backfill_end_time", default_var=None)
    resume = Variable.get("backfill_resume", default_var="false").lower() == "true"

    # Override with context if provided
    if "symbol" in context.get("dag_run", {}).conf:
        symbol = context["dag_run"].conf["symbol"]
    if "start_time" in context.get("dag_run", {}).conf:
        start_time = context["dag_run"].conf["start_time"]
    if "end_time" in context.get("dag_run", {}).conf:
        end_time = context["dag_run"].conf["end_time"]
    if "resume" in context.get("dag_run", {}).conf:
        resume = context["dag_run"].conf["resume"]

    if not start_time or not end_time:
        raise ValueError(
            "start_time and end_time must be provided via Airflow variables or DAG run config"
        )

    # Build command
    script_path = os.path.join(
        os.path.dirname(__file__),
        "..",
        "..",
        "..",
        "..",
        "..",
        "..",
        "..",
        "scripts",
        "backfill_mt5_data.py",
    )

    cmd = [
        sys.executable,
        script_path,
        "--symbol",
        symbol,
        "--start-time",
        start_time,
        "--end-time",
        end_time,
        "--skip-ohlcv",  # OHLCV will be done in separate task
    ]

    if resume:
        cmd.append("--resume")

    # Execute backfill script
    result = subprocess.run(cmd, capture_output=True, text=True, check=True)

    print(f"Backfill output: {result.stdout}")
    if result.stderr:
        print(f"Backfill errors: {result.stderr}")

    return f"Backfill completed for {symbol}"


def aggregate_ohlcv_task(**context):
    """
    Task to aggregate ticks to OHLCV bars
    """
    from airflow.models import Variable

    # Get configuration
    symbol = Variable.get("backfill_symbol", default_var="EURUSD")
    start_time = Variable.get("backfill_start_time", default_var=None)
    end_time = Variable.get("backfill_end_time", default_var=None)
    timeframes = Variable.get(
        "backfill_timeframes", default_var="M1 M5 M15 M30 H1 H4 D1"
    ).split()

    # Override with context if provided
    if "symbol" in context.get("dag_run", {}).conf:
        symbol = context["dag_run"].conf["symbol"]
    if "start_time" in context.get("dag_run", {}).conf:
        start_time = context["dag_run"].conf["start_time"]
    if "end_time" in context.get("dag_run", {}).conf:
        end_time = context["dag_run"].conf["end_time"]
    if "timeframes" in context.get("dag_run", {}).conf:
        timeframes = context["dag_run"].conf["timeframes"].split()

    if not start_time or not end_time:
        raise ValueError("start_time and end_time must be provided")

    # Import aggregation function directly
    from .....database import Database
    from .....utils.ohlcv_aggregator import TickToOHLCVAggregator

    db = Database()

    # Get ticks from database
    from datetime import datetime as dt

    start_dt = dt.fromisoformat(start_time.replace("Z", "+00:00"))
    end_dt = dt.fromisoformat(end_time.replace("Z", "+00:00"))
    hours = int((end_dt - start_dt).total_seconds() / 3600) + 1

    ticks = db.get_recent_ticks(symbol=symbol, limit=1000000, hours=hours)

    if not ticks:
        print(f"No ticks found for {symbol}, skipping aggregation")
        return "No ticks to aggregate"

    # Convert to aggregator format
    tick_list = []
    for tick in ticks:
        tick_datetime = tick.get("event_time") or tick.get("datetime")
        if not tick_datetime:
            continue

        if isinstance(tick_datetime, str):
            try:
                tick_datetime = dt.fromisoformat(tick_datetime.replace("Z", "+00:00"))
            except ValueError:
                continue

        if tick_datetime < start_dt or tick_datetime > end_dt:
            continue

        tick_list.append(
            {
                "timestamp": tick_datetime,
                "bid": tick.get("bid", 0.0),
                "ask": tick.get("ask", 0.0),
                "volume": tick.get("volume"),
            }
        )

    # Aggregate for each timeframe
    aggregator = TickToOHLCVAggregator()
    total_bars = 0

    for timeframe in timeframes:
        bars = aggregator.aggregate_ticks(tick_list, timeframe)

        if not bars:
            continue

        # Prepare bars for database
        bar_list = []
        for bar in bars:
            bar_list.append(
                {
                    "symbol": symbol,
                    "datetime": bar["datetime"],
                    "open": bar["open"],
                    "high": bar["high"],
                    "low": bar["low"],
                    "close": bar["close"],
                    "volume": bar.get("volume"),
                    "timeframe": timeframe,
                }
            )

        # Store bars
        inserted = db.insert_forex_bars_batch(bar_list)
        total_bars += inserted
        print(f"Stored {inserted} {timeframe} bars")

    return f"Aggregated {total_bars} bars across {len(timeframes)} timeframes"


def validate_quality_task(**context):
    """
    Task to validate data quality on backfilled data using Great Expectations
    """
    from airflow.models import Variable
    from datetime import datetime as dt
    from .....database import Database
    from ...data_quality.ge_expectations import (
        validate_batch_and_generate_docs,
    )

    symbol = Variable.get("backfill_symbol", default_var="EURUSD")
    start_time = Variable.get("backfill_start_time", default_var=None)
    end_time = Variable.get("backfill_end_time", default_var=None)

    # Override with context if provided
    if "symbol" in context.get("dag_run", {}).conf:
        symbol = context["dag_run"].conf["symbol"]
    if "start_time" in context.get("dag_run", {}).conf:
        start_time = context["dag_run"].conf["start_time"]
    if "end_time" in context.get("dag_run", {}).conf:
        end_time = context["dag_run"].conf["end_time"]

    if not start_time or not end_time:
        raise ValueError("start_time and end_time must be provided")

    print(f"Running quality checks for {symbol} from {start_time} to {end_time}")

    db = Database()
    start_dt = dt.fromisoformat(start_time.replace("Z", "+00:00"))
    end_dt = dt.fromisoformat(end_time.replace("Z", "+00:00"))
    hours = int((end_dt - start_dt).total_seconds() / 3600) + 1

    # Get ticks for validation
    ticks = db.get_recent_ticks(symbol=symbol, limit=10000, hours=hours)

    if not ticks:
        print(f"No ticks found for {symbol}, skipping validation")
        return "No data to validate"

    # Convert to validation format
    tick_data = []
    for tick in ticks:
        tick_datetime = tick.get("event_time") or tick.get("datetime")
        if not tick_datetime:
            continue

        if isinstance(tick_datetime, str):
            try:
                tick_datetime = dt.fromisoformat(tick_datetime.replace("Z", "+00:00"))
            except ValueError:
                continue

        if tick_datetime < start_dt or tick_datetime > end_dt:
            continue

        tick_data.append(
            {
                "symbol": symbol,
                "datetime": tick_datetime,
                "bid": tick.get("bid", 0.0),
                "ask": tick.get("ask", 0.0),
                "volume": tick.get("volume"),
            }
        )

    # Validate with Great Expectations
    validation_result = validate_batch_and_generate_docs("tick", tick_data)

    if validation_result.get("success"):
        print(
            f"Quality validation passed: {validation_result.get('validated_count')} records"
        )
        if validation_result.get("data_docs_generated"):
            print("Data Docs generated successfully")
    else:
        error = validation_result.get("error", "Unknown error")
        print(f"Quality validation failed: {error}")
        # Don't fail the DAG - quality issues are logged but don't block backfill

    return f"Quality validation completed: {validation_result.get('validated_count', 0)} records validated"


# Define tasks
task_backfill_ticks = PythonOperator(
    task_id="backfill_ticks",
    python_callable=backfill_ticks_task,
    dag=dag,
)

task_aggregate_ohlcv = PythonOperator(
    task_id="aggregate_ohlcv",
    python_callable=aggregate_ohlcv_task,
    dag=dag,
)

task_validate_quality = PythonOperator(
    task_id="validate_quality",
    python_callable=validate_quality_task,
    dag=dag,
)

# Set task dependencies
task_backfill_ticks >> task_aggregate_ohlcv >> task_validate_quality
