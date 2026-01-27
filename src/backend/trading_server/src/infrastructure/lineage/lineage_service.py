"""
Lineage Service Wrapper for Trading Server
Wraps OpenLineage client and stores events in database
"""

import uuid
import json
from typing import Dict, Any, Optional, List
from sqlalchemy import text
from utils.logging_config import get_logger
from utils.time_utils import get_utc_time

# Try to import OpenLineage, but handle gracefully if not available
try:
    from openlineage.client import OpenLineageClient

    # OpenLineage facets not used currently
    # from openlineage.client.facet import (
    #     DataSourceDatasetFacet,
    #     SchemaDatasetFacet,
    #     SchemaField,
    # )

    OPENLINEAGE_AVAILABLE = True
except ImportError:
    OPENLINEAGE_AVAILABLE = False
    OpenLineageClient = None  # type: ignore[misc,assignment]


class LineageService:
    """
    Lineage service wrapper for trading server
    Stores lineage events in database using existing schema
    """

    def __init__(self, database=None):
        """
        Initialize lineage service

        :param database: Database instance (optional, will create if not provided)
        """
        self.logger = get_logger("lineage_service", "lineage_service.log")

        # Lazy import database to avoid circular imports
        if database is None:
            try:
                from database import Database

                self.database = Database()
            except Exception as e:
                self.logger.warning(f"Failed to initialize database: {e}")
                self.database = None
        else:
            self.database = database

        # Initialize OpenLineage client if available (optional)
        self.openlineage_client = None
        if OPENLINEAGE_AVAILABLE:
            try:
                # Configure OpenLineage client (can use HTTP transport or direct DB)
                # For now, we'll use database storage only
                self.openlineage_client = None  # Can be configured later if needed
            except Exception as e:
                self.logger.warning(f"Failed to initialize OpenLineage client: {e}")

        # Track active runs
        self._active_runs: Dict[str, Dict[str, Any]] = {}

    def start_run(
        self,
        job_name: str,
        namespace: str = "trading_data",
        run_id: Optional[str] = None,
        inputs: Optional[List[Dict[str, str]]] = None,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> str:
        """
        Start a lineage run and emit RunEvent.START

        :param job_name: Job name (e.g., "mt5_tick_collection_EURUSD")
        :param namespace: Namespace (default: "trading_data")
        :param run_id: Optional run ID (will generate UUID if not provided)
        :param inputs: List of input datasets [{"dataset_id": "...", "namespace": "..."}]
        :param metadata: Optional metadata dictionary
        :return: Run ID
        """
        if self.database is None:
            self.logger.warning("Database not available, skipping lineage tracking")
            return str(uuid.uuid4())

        if run_id is None:
            run_id = str(uuid.uuid4())

        start_time = get_utc_time()
        inputs = inputs or []
        metadata = metadata or {}

        try:
            # Ensure job exists
            self._ensure_job_exists(job_name, namespace)

            # Insert run record
            with self.database.execute_query() as conn:
                conn.execute(
                    text("""
                        INSERT INTO lineage_runs (run_id, job_name, namespace, start_time, status, metadata)
                        VALUES (:run_id, :job_name, :namespace, :start_time, :status, :metadata::jsonb)
                        ON CONFLICT (run_id) DO UPDATE SET
                            start_time = EXCLUDED.start_time,
                            status = EXCLUDED.status,
                            metadata = EXCLUDED.metadata
                    """),
                    {
                        "run_id": run_id,
                        "job_name": job_name,
                        "namespace": namespace,
                        "start_time": start_time,
                        "status": "RUNNING",
                        "metadata": json.dumps(metadata),
                    },
                )

                # Insert input datasets
                for input_dataset in inputs:
                    dataset_id = input_dataset.get("dataset_id")
                    if dataset_id is None:
                        continue
                    input_namespace = input_dataset.get("namespace", namespace)
                    self._ensure_dataset_exists(dataset_id, input_namespace, conn)
                    conn.execute(
                        text("""
                            INSERT INTO lineage_run_datasets (run_id, dataset_id, io_type, namespace)
                            VALUES (:run_id, :dataset_id, 'input', :namespace)
                            ON CONFLICT (run_id, dataset_id, io_type) DO NOTHING
                        """),
                        {
                            "run_id": run_id,
                            "dataset_id": dataset_id,
                            "namespace": input_namespace,
                        },
                    )

            # Track active run
            self._active_runs[run_id] = {
                "job_name": job_name,
                "namespace": namespace,
                "start_time": start_time,
                "inputs": inputs,
            }

            # Update metrics
            try:
                from monitoring.metrics import (
                    lineage_runs_total,
                    lineage_events_emitted_total,
                )

                lineage_runs_total.labels(
                    job_name=job_name, namespace=namespace, status="RUNNING"
                ).inc()
                lineage_events_emitted_total.labels(event_type="START").inc()
            except Exception as e:
                self.logger.debug(f"Failed to update metrics: {e}")

            self.logger.debug(f"Started lineage run: {run_id} for job {job_name}")
            return run_id

        except Exception as e:
            self.logger.error(f"Failed to start lineage run: {e}", exc_info=True)
            # Return run_id anyway so caller can continue
            return run_id

    def complete_run(
        self,
        run_id: str,
        outputs: Optional[List[Dict[str, str]]] = None,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> None:
        """
        Complete a lineage run and emit RunEvent.COMPLETE

        :param run_id: Run ID
        :param outputs: List of output datasets [{"dataset_id": "...", "namespace": "..."}]
        :param metadata: Optional metadata dictionary
        """
        if self.database is None:
            return

        if run_id not in self._active_runs:
            self.logger.warning(f"Completing unknown run: {run_id}")
            return

        end_time = get_utc_time()
        outputs = outputs or []
        metadata = metadata or {}
        run_info = self._active_runs[run_id]

        try:
            # Update existing metadata
            existing_metadata = metadata.copy()

            with self.database.execute_query() as conn:
                # Get existing metadata
                result = conn.execute(
                    text("SELECT metadata FROM lineage_runs WHERE run_id = :run_id"),
                    {"run_id": run_id},
                ).fetchone()
                if result and result[0]:
                    try:
                        existing_metadata.update(json.loads(result[0]))
                    except (ValueError, TypeError, KeyError):
                        pass

                # Update run record
                conn.execute(
                    text("""
                        UPDATE lineage_runs
                        SET end_time = :end_time,
                            status = :status,
                            metadata = :metadata::jsonb
                        WHERE run_id = :run_id
                    """),
                    {
                        "run_id": run_id,
                        "end_time": end_time,
                        "status": "COMPLETE",
                        "metadata": json.dumps(existing_metadata),
                    },
                )

                # Insert output datasets
                for output_dataset in outputs:
                    dataset_id = output_dataset.get("dataset_id")
                    dataset_id = output_dataset.get("dataset_id")
                    if dataset_id is None:
                        continue
                    output_namespace = output_dataset.get(
                        "namespace", run_info["namespace"]
                    )
                    schema = output_dataset.get("schema")
                    if isinstance(schema, str):
                        # Convert string schema to dict if needed
                        try:
                            schema = json.loads(schema) if schema else None
                        except (json.JSONDecodeError, TypeError):
                            schema = None
                    self._ensure_dataset_exists(
                        dataset_id,
                        output_namespace,
                        conn,
                        schema=schema,
                        schema_version=output_dataset.get("schema_version"),
                    )
                    conn.execute(
                        text("""
                            INSERT INTO lineage_run_datasets (run_id, dataset_id, io_type, namespace)
                            VALUES (:run_id, :dataset_id, 'output', :namespace)
                            ON CONFLICT (run_id, dataset_id, io_type) DO NOTHING
                        """),
                        {
                            "run_id": run_id,
                            "dataset_id": dataset_id,
                            "namespace": output_namespace,
                        },
                    )

            # Update job latest_run_id
            self._update_job_latest_run(
                run_info["job_name"], run_info["namespace"], run_id
            )

            # Remove from active runs
            del self._active_runs[run_id]

            # Update metrics
            try:
                from monitoring.metrics import (
                    lineage_runs_total,
                    lineage_runs_duration_seconds,
                    lineage_events_emitted_total,
                )

                duration = (end_time - run_info["start_time"]).total_seconds()
                lineage_runs_total.labels(
                    job_name=run_info["job_name"],
                    namespace=run_info["namespace"],
                    status="COMPLETE",
                ).inc()
                lineage_runs_duration_seconds.labels(
                    job_name=run_info["job_name"], namespace=run_info["namespace"]
                ).observe(duration)
                lineage_events_emitted_total.labels(event_type="COMPLETE").inc()
            except Exception as e:
                self.logger.debug(f"Failed to update metrics: {e}")

            self.logger.debug(f"Completed lineage run: {run_id}")

        except Exception as e:
            self.logger.error(f"Failed to complete lineage run: {e}", exc_info=True)

    def fail_run(
        self,
        run_id: str,
        error_message: str,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> None:
        """
        Mark a lineage run as failed and emit RunEvent.FAIL

        :param run_id: Run ID
        :param error_message: Error message
        :param metadata: Optional metadata dictionary
        """
        if self.database is None:
            return

        end_time = get_utc_time()
        metadata = metadata or {}
        run_info = self._active_runs.get(run_id, {})

        try:
            with self.database.execute_query() as conn:
                # Get existing metadata
                existing_metadata = metadata.copy()
                result = conn.execute(
                    text("SELECT metadata FROM lineage_runs WHERE run_id = :run_id"),
                    {"run_id": run_id},
                ).fetchone()
                if result and result[0]:
                    try:
                        existing_metadata.update(json.loads(result[0]))
                    except (ValueError, TypeError, KeyError):
                        pass

                # Update run record
                conn.execute(
                    text("""
                        UPDATE lineage_runs
                        SET end_time = :end_time,
                            status = :status,
                            error_message = :error_message,
                            metadata = :metadata::jsonb
                        WHERE run_id = :run_id
                    """),
                    {
                        "run_id": run_id,
                        "end_time": end_time,
                        "status": "FAILED",
                        "error_message": error_message,
                        "metadata": json.dumps(existing_metadata),
                    },
                )

            # Remove from active runs
            if run_id in self._active_runs:
                del self._active_runs[run_id]

            # Update metrics
            try:
                from monitoring.metrics import (
                    lineage_runs_total,
                    lineage_runs_failed_total,
                    lineage_events_emitted_total,
                )

                job_name = run_info.get("job_name", "unknown")
                namespace = run_info.get("namespace", "unknown")
                lineage_runs_total.labels(
                    job_name=job_name, namespace=namespace, status="FAILED"
                ).inc()
                lineage_runs_failed_total.labels(
                    job_name=job_name, namespace=namespace
                ).inc()
                lineage_events_emitted_total.labels(event_type="FAIL").inc()
            except Exception as e:
                self.logger.debug(f"Failed to update metrics: {e}")

            self.logger.debug(f"Failed lineage run: {run_id} - {error_message}")

        except Exception as e:
            self.logger.error(
                f"Failed to mark lineage run as failed: {e}", exc_info=True
            )

    def emit_dataset(
        self,
        dataset_name: str,
        namespace: str = "trading_data",
        schema: Optional[Dict[str, Any]] = None,
        schema_version: Optional[str] = None,
        facets: Optional[Dict[str, Any]] = None,
    ) -> None:
        """
        Emit DatasetEvent for a dataset

        :param dataset_name: Dataset name
        :param namespace: Namespace
        :param schema: Schema dictionary
        :param schema_version: Schema version
        :param facets: Optional facets dictionary
        """
        if self.database is None:
            return

        dataset_id = f"{namespace}:{dataset_name}"

        try:
            with self.database.execute_query() as conn:
                self._ensure_dataset_exists(
                    dataset_id,
                    namespace,
                    conn,
                    dataset_name,
                    schema,
                    schema_version,
                )

            # Update metrics
            try:
                from monitoring.metrics import (
                    lineage_events_emitted_total,
                    lineage_datasets_total,
                )

                lineage_events_emitted_total.labels(event_type="DATASET").inc()
                lineage_datasets_total.labels(namespace=namespace).inc()
            except Exception as e:
                self.logger.debug(f"Failed to update metrics: {e}")

            self.logger.debug(f"Emitted dataset event: {dataset_id}")

        except Exception as e:
            self.logger.error(f"Failed to emit dataset event: {e}", exc_info=True)

    def _ensure_job_exists(self, job_name: str, namespace: str) -> None:
        """Ensure job exists in lineage_jobs table"""
        if self.database is None:
            return

        try:
            with self.database.execute_query() as conn:
                conn.execute(
                    text("""
                        INSERT INTO lineage_jobs (job_name, namespace, description)
                        VALUES (:job_name, :namespace, :description)
                        ON CONFLICT (job_name, namespace) DO NOTHING
                    """),
                    {
                        "job_name": job_name,
                        "namespace": namespace,
                        "description": f"Data collection job: {job_name}",
                    },
                )
        except Exception as e:
            self.logger.warning(f"Failed to ensure job exists: {e}")

    def _ensure_dataset_exists(
        self,
        dataset_id: str,
        namespace: str,
        conn,
        name: Optional[str] = None,
        schema: Optional[Dict[str, Any]] = None,
        schema_version: Optional[str] = None,
    ) -> None:
        """Ensure dataset exists in lineage_datasets table"""
        if name is None:
            # Extract name from dataset_id (format: "namespace:name")
            if ":" in dataset_id:
                name = dataset_id.split(":", 1)[1]
            else:
                name = dataset_id

        try:
            conn.execute(
                text("""
                    INSERT INTO lineage_datasets (dataset_id, name, namespace, schema_version, schema_json)
                    VALUES (:dataset_id, :name, :namespace, :schema_version, :schema_json::jsonb)
                    ON CONFLICT (dataset_id, namespace) DO UPDATE SET
                        schema_version = COALESCE(EXCLUDED.schema_version, lineage_datasets.schema_version),
                        schema_json = COALESCE(EXCLUDED.schema_json, lineage_datasets.schema_json),
                        updated_at = CURRENT_TIMESTAMP
                """),
                {
                    "dataset_id": dataset_id,
                    "name": name,
                    "namespace": namespace,
                    "schema_version": schema_version,
                    "schema_json": json.dumps(schema) if schema else None,
                },
            )
        except Exception as e:
            self.logger.warning(f"Failed to ensure dataset exists: {e}")

    def _update_job_latest_run(
        self, job_name: str, namespace: str, run_id: str
    ) -> None:
        """Update job's latest_run_id"""
        if self.database is None:
            return

        try:
            with self.database.execute_query() as conn:
                conn.execute(
                    text("""
                        UPDATE lineage_jobs
                        SET latest_run_id = :run_id,
                            updated_at = CURRENT_TIMESTAMP
                        WHERE job_name = :job_name AND namespace = :namespace
                    """),
                    {
                        "job_name": job_name,
                        "namespace": namespace,
                        "run_id": run_id,
                    },
                )
        except Exception as e:
            self.logger.warning(f"Failed to update job latest run: {e}")
