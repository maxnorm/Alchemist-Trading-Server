"""
Lineage API endpoints
"""

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session
from typing import Optional, List, Dict, Any
from pydantic import BaseModel, Field
from dependencies import get_db
from middleware.auth import get_current_user
import logging

from services.lineage_service import LineageService

logger = logging.getLogger(__name__)

router = APIRouter()


# Response models
class RunLineageResponse(BaseModel):
    """Response model for run lineage"""

    run_id: str
    job_name: str
    namespace: str
    start_time: Optional[str] = None
    end_time: Optional[str] = None
    status: str
    error_message: Optional[str] = None
    metadata: Dict[str, Any] = {}
    inputs: List[Dict[str, str]] = []
    outputs: List[Dict[str, str]] = []


class DatasetLineageResponse(BaseModel):
    """Response model for dataset lineage"""

    dataset_id: str
    name: str
    namespace: str
    schema_version: Optional[str] = None
    schema_data: Optional[Dict[str, Any]] = Field(None, alias="schema")
    produced_by: List[Dict[str, Any]] = []
    consumed_by: List[Dict[str, Any]] = []

    model_config = {"populate_by_name": True}


class JobLineageResponse(BaseModel):
    """Response model for job lineage"""

    id: int
    job_name: str
    namespace: str
    description: Optional[str] = None
    latest_run_id: Optional[str] = None
    created_at: Optional[str] = None
    updated_at: Optional[str] = None
    runs: List[Dict[str, Any]] = []


class RunListItem(BaseModel):
    """Response model for run list item"""

    run_id: str
    job_name: str
    namespace: str
    start_time: Optional[str] = None
    end_time: Optional[str] = None
    status: str
    error_message: Optional[str] = None


class DatasetListItem(BaseModel):
    """Response model for dataset list item"""

    dataset_id: str
    name: str
    namespace: str
    schema_version: Optional[str] = None
    created_at: Optional[str] = None
    updated_at: Optional[str] = None


@router.get("/lineage/runs/{run_id}", response_model=RunLineageResponse)
async def get_run_lineage(
    run_id: str,
    user: Dict = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """
    Get run details and lineage

    :param run_id: Run ID
    :return: Run lineage information
    """
    try:
        lineage = LineageService.get_run_lineage(db, run_id)
        if not lineage:
            raise HTTPException(status_code=404, detail=f"Run not found: {run_id}")
        return RunLineageResponse(**lineage)
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error fetching run lineage for {run_id}: {e}", exc_info=True)
        raise HTTPException(
            status_code=500, detail=f"Failed to fetch run lineage: {str(e)}"
        )


@router.get(
    "/lineage/datasets/{namespace}/{dataset_name}",
    response_model=DatasetLineageResponse,
)
async def get_dataset_lineage(
    dataset_name: str,
    namespace: str,
    user: Dict = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """
    Get dataset lineage (upstream/downstream)

    :param dataset_name: Dataset name
    :param namespace: Namespace
    :return: Dataset lineage information
    """
    try:
        lineage = LineageService.get_dataset_lineage(db, dataset_name, namespace)
        if not lineage:
            raise HTTPException(
                status_code=404,
                detail=f"Dataset not found: {namespace}:{dataset_name}",
            )
        return DatasetLineageResponse(**lineage)
    except HTTPException:
        raise
    except Exception as e:
        logger.error(
            f"Error fetching dataset lineage for {namespace}:{dataset_name}: {e}",
            exc_info=True,
        )
        raise HTTPException(
            status_code=500, detail=f"Failed to fetch dataset lineage: {str(e)}"
        )


@router.get("/lineage/jobs/{namespace}/{job_name}", response_model=JobLineageResponse)
async def get_job_lineage(
    job_name: str,
    namespace: str,
    user: Dict = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """
    Get job lineage and run history

    :param job_name: Job name
    :param namespace: Namespace
    :return: Job lineage information
    """
    try:
        lineage = LineageService.get_job_lineage(db, job_name, namespace)
        if not lineage:
            raise HTTPException(
                status_code=404,
                detail=f"Job not found: {namespace}:{job_name}",
            )
        return JobLineageResponse(**lineage)
    except HTTPException:
        raise
    except Exception as e:
        logger.error(
            f"Error fetching job lineage for {namespace}:{job_name}: {e}",
            exc_info=True,
        )
        raise HTTPException(
            status_code=500, detail=f"Failed to fetch job lineage: {str(e)}"
        )


@router.get("/lineage/runs", response_model=List[RunListItem])
async def list_runs(
    job_name: Optional[str] = Query(None, description="Filter by job name"),
    namespace: Optional[str] = Query(None, description="Filter by namespace"),
    status: Optional[str] = Query(None, description="Filter by status"),
    limit: int = Query(100, ge=1, le=1000, description="Maximum number of results"),
    offset: int = Query(0, ge=0, description="Offset for pagination"),
    user: Dict = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """
    List runs with filters

    :param job_name: Filter by job name
    :param namespace: Filter by namespace
    :param status: Filter by status (RUNNING, COMPLETE, FAILED, ABORTED)
    :param limit: Maximum number of results
    :param offset: Offset for pagination
    :return: List of runs
    """
    try:
        runs = LineageService.list_runs(
            db,
            job_name=job_name,
            namespace=namespace,
            status=status,
            limit=limit,
            offset=offset,
        )
        return [RunListItem(**run) for run in runs]
    except Exception as e:
        logger.error(f"Error listing runs: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Failed to list runs: {str(e)}")


@router.get("/lineage/datasets", response_model=List[DatasetListItem])
async def list_datasets(
    namespace: Optional[str] = Query(None, description="Filter by namespace"),
    limit: int = Query(100, ge=1, le=1000, description="Maximum number of results"),
    user: Dict = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """
    List all datasets

    :param namespace: Filter by namespace
    :param limit: Maximum number of results
    :return: List of datasets
    """
    try:
        datasets = LineageService.list_datasets(db, namespace=namespace, limit=limit)
        return [DatasetListItem(**dataset) for dataset in datasets]
    except Exception as e:
        logger.error(f"Error listing datasets: {e}", exc_info=True)
        raise HTTPException(
            status_code=500, detail=f"Failed to list datasets: {str(e)}"
        )
