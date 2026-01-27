"""
Lineage Service
Wraps lineage tracking for use in the FastAPI service
"""

import json
import logging
from typing import Dict, Optional, List, Any
from sqlalchemy.orm import Session
from sqlalchemy import text

logger = logging.getLogger(__name__)


class LineageService:
    """
    Service layer for Lineage operations
    Uses SQLAlchemy sessions for database access
    """

    @staticmethod
    def get_run_lineage(db: Session, run_id: str) -> Optional[Dict[str, Any]]:
        """
        Get lineage information for a run

        :param db: Database session
        :param run_id: Run ID
        :return: Lineage information or None
        """
        try:
            # Get run details
            run_query = text("""
                SELECT run_id, job_name, namespace, start_time, end_time, status, error_message, metadata
                FROM lineage_runs
                WHERE run_id = :run_id
            """)
            run_result = db.execute(run_query, {"run_id": run_id}).fetchone()

            if not run_result:
                return None

            # Get input/output datasets
            datasets_query = text("""
                SELECT dataset_id, io_type, namespace
                FROM lineage_run_datasets
                WHERE run_id = :run_id
            """)
            datasets_result = db.execute(datasets_query, {"run_id": run_id}).fetchall()

            inputs = []
            outputs = []
            for dataset_id, io_type, namespace in datasets_result:
                dataset_info = {"dataset_id": dataset_id, "namespace": namespace}
                if io_type == "input":
                    inputs.append(dataset_info)
                else:
                    outputs.append(dataset_info)

            return {
                "run_id": run_result[0],
                "job_name": run_result[1],
                "namespace": run_result[2],
                "start_time": run_result[3].isoformat() if run_result[3] else None,
                "end_time": run_result[4].isoformat() if run_result[4] else None,
                "status": run_result[5],
                "error_message": run_result[6],
                "metadata": json.loads(run_result[7]) if run_result[7] else {},
                "inputs": inputs,
                "outputs": outputs,
            }
        except Exception as e:
            logger.error(f"Failed to get run lineage for {run_id}: {e}")
            raise

    @staticmethod
    def get_dataset_lineage(
        db: Session, dataset_name: str, namespace: str
    ) -> Optional[Dict[str, Any]]:
        """
        Get lineage information for a dataset

        :param db: Database session
        :param dataset_name: Dataset name
        :param namespace: Namespace
        :return: Lineage information or None
        """
        dataset_id = f"{namespace}:{dataset_name}"

        try:
            # Get dataset details
            dataset_query = text("""
                SELECT dataset_id, name, namespace, schema_version, schema_json
                FROM lineage_datasets
                WHERE dataset_id = :dataset_id AND namespace = :namespace
            """)
            dataset_result = db.execute(
                dataset_query, {"dataset_id": dataset_id, "namespace": namespace}
            ).fetchone()

            if not dataset_result:
                return None

            # Get runs that produced this dataset (outputs)
            output_runs_query = text("""
                SELECT lr.run_id, lr.job_name, lr.start_time, lr.end_time, lr.status
                FROM lineage_runs lr
                JOIN lineage_run_datasets lrd ON lr.run_id = lrd.run_id
                WHERE lrd.dataset_id = :dataset_id AND lrd.io_type = 'output'
                ORDER BY lr.start_time DESC
                LIMIT 100
            """)
            output_runs = db.execute(
                output_runs_query, {"dataset_id": dataset_id}
            ).fetchall()

            # Get runs that consumed this dataset (inputs)
            input_runs_query = text("""
                SELECT lr.run_id, lr.job_name, lr.start_time, lr.end_time, lr.status
                FROM lineage_runs lr
                JOIN lineage_run_datasets lrd ON lr.run_id = lrd.run_id
                WHERE lrd.dataset_id = :dataset_id AND lrd.io_type = 'input'
                ORDER BY lr.start_time DESC
                LIMIT 100
            """)
            input_runs = db.execute(
                input_runs_query, {"dataset_id": dataset_id}
            ).fetchall()

            return {
                "dataset_id": dataset_result[0],
                "name": dataset_result[1],
                "namespace": dataset_result[2],
                "schema_version": dataset_result[3],
                "schema": json.loads(dataset_result[4]) if dataset_result[4] else None,
                "produced_by": [
                    {
                        "run_id": run[0],
                        "job_name": run[1],
                        "start_time": run[2].isoformat() if run[2] else None,
                        "end_time": run[3].isoformat() if run[3] else None,
                        "status": run[4],
                    }
                    for run in output_runs
                ],
                "consumed_by": [
                    {
                        "run_id": run[0],
                        "job_name": run[1],
                        "start_time": run[2].isoformat() if run[2] else None,
                        "end_time": run[3].isoformat() if run[3] else None,
                        "status": run[4],
                    }
                    for run in input_runs
                ],
            }
        except Exception as e:
            logger.error(f"Failed to get dataset lineage for {dataset_name}: {e}")
            raise

    @staticmethod
    def get_job_lineage(
        db: Session, job_name: str, namespace: str
    ) -> Optional[Dict[str, Any]]:
        """
        Get lineage information for a job

        :param db: Database session
        :param job_name: Job name
        :param namespace: Namespace
        :return: Lineage information or None
        """
        try:
            # Get job details
            job_query = text("""
                SELECT id, job_name, namespace, description, latest_run_id, created_at, updated_at
                FROM lineage_jobs
                WHERE job_name = :job_name AND namespace = :namespace
            """)
            job_result = db.execute(
                job_query, {"job_name": job_name, "namespace": namespace}
            ).fetchone()

            if not job_result:
                return None

            # Get recent runs for this job
            runs_query = text("""
                SELECT run_id, start_time, end_time, status, error_message
                FROM lineage_runs
                WHERE job_name = :job_name AND namespace = :namespace
                ORDER BY start_time DESC
                LIMIT 100
            """)
            runs = db.execute(
                runs_query, {"job_name": job_name, "namespace": namespace}
            ).fetchall()

            return {
                "id": job_result[0],
                "job_name": job_result[1],
                "namespace": job_result[2],
                "description": job_result[3],
                "latest_run_id": job_result[4],
                "created_at": job_result[5].isoformat() if job_result[5] else None,
                "updated_at": job_result[6].isoformat() if job_result[6] else None,
                "runs": [
                    {
                        "run_id": run[0],
                        "start_time": run[1].isoformat() if run[1] else None,
                        "end_time": run[2].isoformat() if run[2] else None,
                        "status": run[3],
                        "error_message": run[4],
                    }
                    for run in runs
                ],
            }
        except Exception as e:
            logger.error(f"Failed to get job lineage for {job_name}: {e}")
            raise

    @staticmethod
    def list_runs(
        db: Session,
        job_name: Optional[str] = None,
        namespace: Optional[str] = None,
        status: Optional[str] = None,
        limit: int = 100,
        offset: int = 0,
    ) -> List[Dict[str, Any]]:
        """
        List runs with filters

        :param db: Database session
        :param job_name: Filter by job name
        :param namespace: Filter by namespace
        :param status: Filter by status
        :param limit: Maximum number of results
        :param offset: Offset for pagination
        :return: List of run dictionaries
        """
        conditions = []
        params: Dict[str, Any] = {}

        if job_name:
            conditions.append("job_name = :job_name")
            params["job_name"] = job_name
        if namespace:
            conditions.append("namespace = :namespace")
            params["namespace"] = namespace
        if status:
            conditions.append("status = :status")
            params["status"] = status

        where_clause = " AND ".join(conditions) if conditions else "1=1"

        query = text(f"""
            SELECT run_id, job_name, namespace, start_time, end_time, status, error_message
            FROM lineage_runs
            WHERE {where_clause}
            ORDER BY start_time DESC
            LIMIT :limit OFFSET :offset
        """)
        params["limit"] = limit
        params["offset"] = offset

        try:
            result = db.execute(query, params)
            runs = []
            for row in result:
                runs.append(
                    {
                        "run_id": row[0],
                        "job_name": row[1],
                        "namespace": row[2],
                        "start_time": row[3].isoformat() if row[3] else None,
                        "end_time": row[4].isoformat() if row[4] else None,
                        "status": row[5],
                        "error_message": row[6],
                    }
                )
            return runs
        except Exception as e:
            logger.error(f"Failed to list runs: {e}")
            raise

    @staticmethod
    def list_datasets(
        db: Session, namespace: Optional[str] = None, limit: int = 100
    ) -> List[Dict[str, Any]]:
        """
        List all datasets

        :param db: Database session
        :param namespace: Filter by namespace
        :param limit: Maximum number of results
        :return: List of dataset dictionaries
        """
        conditions = []
        params: Dict[str, Any] = {}

        if namespace:
            conditions.append("namespace = :namespace")
            params["namespace"] = namespace

        where_clause = " AND ".join(conditions) if conditions else "1=1"

        query = text(f"""
            SELECT dataset_id, name, namespace, schema_version, created_at, updated_at
            FROM lineage_datasets
            WHERE {where_clause}
            ORDER BY created_at DESC
            LIMIT :limit
        """)
        params["limit"] = limit

        try:
            result = db.execute(query, params)
            datasets = []
            for row in result:
                datasets.append(
                    {
                        "dataset_id": row[0],
                        "name": row[1],
                        "namespace": row[2],
                        "schema_version": row[3],
                        "created_at": row[4].isoformat() if row[4] else None,
                        "updated_at": row[5].isoformat() if row[5] else None,
                    }
                )
            return datasets
        except Exception as e:
            logger.error(f"Failed to list datasets: {e}")
            raise
