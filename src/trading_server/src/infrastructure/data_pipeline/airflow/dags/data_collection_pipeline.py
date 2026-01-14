"""
Data Collection Pipeline DAG
Hourly data collection from various sources
"""

from datetime import timedelta
from airflow import DAG
from airflow.operators.python import PythonOperator
from airflow.utils.dates import days_ago
import logging

logger = logging.getLogger(__name__)


def invoke_celery_task(task_func, **kwargs):
    """
    Wrapper function to properly invoke Celery tasks from Airflow.
    Uses .delay() to queue the task and .get() to wait for result.

    :param task_func: Celery task function
    :param kwargs: Additional context from Airflow
    :return: Task result
    """
    try:
        # Invoke Celery task asynchronously
        result = task_func.delay()
        # Wait for result (with timeout)
        task_result = result.get(timeout=1800)  # 30 minute timeout
        logger.info(f"Celery task {task_func.name} completed: {task_result}")
        return task_result
    except Exception as e:
        logger.error(f"Celery task {task_func.name} failed: {e}", exc_info=True)
        raise


def collect_mt5_data_wrapper(**context):
    """Wrapper to invoke collect_mt5_data Celery task"""
    from infrastructure.data_pipeline.tasks.market_data_tasks import collect_mt5_data
    from datetime import datetime, timedelta

    # Get symbol from DAG run config or use default
    symbol = context.get("dag_run", {}).conf.get("symbol", "EURUSD")

    # Collect data from last hour
    end_time = datetime.now()
    start_time = end_time - timedelta(hours=1)

    # Invoke Celery task with parameters
    try:
        result = collect_mt5_data.delay(
            symbol=symbol, start_time=start_time, end_time=end_time
        )
        task_result = result.get(timeout=1800)  # 30 minute timeout
        logger.info(f"Celery task collect_mt5_data completed: {task_result}")
        return task_result
    except Exception as e:
        logger.error(f"Celery task collect_mt5_data failed: {e}", exc_info=True)
        raise


def collect_economic_calendar_wrapper(**context):
    """
    Placeholder task for economic calendar collection
    TODO: Implement actual economic calendar collection task
    """
    logger.info("Collecting economic calendar data...")
    # TODO: Implement actual economic calendar collection
    return {"status": "success", "message": "Economic calendar collection completed"}


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
    "data_collection_pipeline",
    default_args=default_args,
    description="Hourly data collection from MT5 and other sources",
    schedule_interval="@hourly",  # Run every hour
    start_date=days_ago(1),
    catchup=False,  # Don't backfill on first run
    max_active_runs=1,
    tags=["data_collection", "hourly"],
)

# Define tasks
task_mt5 = PythonOperator(
    task_id="collect_mt5_data",
    python_callable=collect_mt5_data_wrapper,
    dag=dag,
)

task_economic = PythonOperator(
    task_id="collect_economic_calendar",
    python_callable=collect_economic_calendar_wrapper,
    dag=dag,
)

# Set task dependencies (run in parallel)
# Both tasks can run independently
[task_mt5, task_economic]
