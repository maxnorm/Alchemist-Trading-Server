"""
Alternative Data Collection DAG
Collects news, sentiment, and macroeconomic indicators from multiple sources
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


def collect_rss_news_wrapper(**context):
    """Wrapper to invoke collect_rss_news Celery task"""
    from infrastructure.data_pipeline.tasks.news_data_tasks import collect_rss_news

    return invoke_celery_task(collect_rss_news, **context)


def collect_web_scraping_news_wrapper(**context):
    """Wrapper to invoke collect_web_scraping_news Celery task"""
    from infrastructure.data_pipeline.tasks.news_data_tasks import (
        collect_web_scraping_news,
    )

    return invoke_celery_task(collect_web_scraping_news, **context)


def collect_fred_indicators_wrapper(**context):
    """Wrapper to invoke collect_fred_indicators Celery task"""
    from infrastructure.data_pipeline.tasks.economic_data_tasks import (
        collect_fred_indicators,
    )

    return invoke_celery_task(collect_fred_indicators, **context)


def collect_world_bank_indicators_wrapper(**context):
    """Wrapper to invoke collect_world_bank_indicators Celery task"""
    from infrastructure.data_pipeline.tasks.economic_data_tasks import (
        collect_world_bank_indicators,
    )

    return invoke_celery_task(collect_world_bank_indicators, **context)


def collect_ecb_indicators_wrapper(**context):
    """Wrapper to invoke collect_ecb_indicators Celery task"""
    from infrastructure.data_pipeline.tasks.economic_data_tasks import (
        collect_ecb_indicators,
    )

    return invoke_celery_task(collect_ecb_indicators, **context)


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
    "alternative_data_collection",
    default_args=default_args,
    description="Alternative data collection: news, sentiment, and economic indicators",
    schedule_interval="*/15 * * * *",  # Run every 15 minutes for news
    start_date=days_ago(1),
    catchup=False,
    max_active_runs=1,
    tags=["alternative_data", "news", "economic_indicators", "phase3"],
)

# News collection tasks (run every 15 minutes)
task_rss_news = PythonOperator(
    task_id="collect_rss_news",
    python_callable=collect_rss_news_wrapper,
    dag=dag,
)

task_web_scraping_news = PythonOperator(
    task_id="collect_web_scraping_news",
    python_callable=collect_web_scraping_news_wrapper,
    dag=dag,
)

# Economic indicator tasks
# FRED: Daily at 9 AM UTC
task_fred_indicators = PythonOperator(
    task_id="collect_fred_indicators",
    python_callable=collect_fred_indicators_wrapper,
    dag=dag,
)

# World Bank: Monthly (1st of month at 10 AM UTC)
task_world_bank_indicators = PythonOperator(
    task_id="collect_world_bank_indicators",
    python_callable=collect_world_bank_indicators_wrapper,
    dag=dag,
)

# ECB: Daily at 10 AM UTC
task_ecb_indicators = PythonOperator(
    task_id="collect_ecb_indicators",
    python_callable=collect_ecb_indicators_wrapper,
    dag=dag,
)

# Set task dependencies
# News tasks can run in parallel
[task_rss_news, task_web_scraping_news]

# Economic indicator tasks can also run in parallel
[task_fred_indicators, task_world_bank_indicators, task_ecb_indicators]

# Note: In production, you might want separate DAGs for different schedules:
# - News: Every 15 minutes
# - FRED: Daily at 9 AM
# - ECB: Daily at 10 AM
# - World Bank: Monthly
#
# For now, all tasks run on the same schedule but connectors handle their own update logic
