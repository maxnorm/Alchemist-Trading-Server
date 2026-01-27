"""
Schema Registry API endpoints
"""

from fastapi import APIRouter, Depends, HTTPException, Body
from fastapi.responses import FileResponse, HTMLResponse
from sqlalchemy.orm import Session
from typing import Optional, Dict, Any, List
from pydantic import BaseModel, Field
from pathlib import Path
from dependencies import get_db
from middleware.auth import get_current_user
import logging

from services.schema_registry import SchemaRegistryService

logger = logging.getLogger(__name__)

router = APIRouter()


# Request/Response models
class SchemaRegisterRequest(BaseModel):
    """Request model for registering a schema"""

    version: str = Field(..., description="Semantic version (MAJOR.MINOR.PATCH)")
    schema_data: Dict[str, Any] = Field(
        ..., alias="schema", description="JSON Schema definition (Draft 7 format)"
    )
    compatibility_mode: str = Field(
        default="NONE",
        description="Compatibility mode: BACKWARD, FORWARD, FULL, or NONE",
    )

    model_config = {"populate_by_name": True}


class SchemaResponse(BaseModel):
    """Response model for schema"""

    id: int
    data_type: str
    version: str
    schema_json_data: Dict[str, Any] = Field(..., alias="schema_json")
    compatibility_mode: str
    status: str
    created_at: Optional[str] = None
    updated_at: Optional[str] = None

    model_config = {"populate_by_name": True}


class SchemaVersionListResponse(BaseModel):
    """Response model for schema version list"""

    data_type: str
    versions: List[SchemaResponse]


class CompatibilityCheckRequest(BaseModel):
    """Request model for compatibility check"""

    old_schema: Dict[str, Any] = Field(..., description="Old schema definition")
    new_schema: Dict[str, Any] = Field(..., description="New schema definition")
    mode: str = Field(
        ..., description="Compatibility mode: BACKWARD, FORWARD, FULL, or NONE"
    )


class CompatibilityCheckResponse(BaseModel):
    """Response model for compatibility check"""

    compatible: bool
    message: Optional[str] = None


@router.get("/schema/{data_type}", response_model=SchemaResponse)
async def get_latest_schema(
    data_type: str,
    user: Dict = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """
    Get latest schema for a data type

    :param data_type: Data type identifier (e.g., "tick", "bar")
    :return: Latest schema
    """
    try:
        schema = SchemaRegistryService.get_schema(db, data_type)
        if not schema:
            raise HTTPException(
                status_code=404, detail=f"No schema found for data type: {data_type}"
            )
        return SchemaResponse(**schema)
    except HTTPException:
        raise
    except Exception as e:
        logger.error(
            f"Error fetching latest schema for {data_type}: {e}", exc_info=True
        )
        raise HTTPException(status_code=500, detail=f"Failed to fetch schema: {str(e)}")


@router.get("/schema/{data_type}/{version}", response_model=SchemaResponse)
async def get_schema_version(
    data_type: str,
    version: str,
    user: Dict = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """
    Get specific schema version for a data type

    :param data_type: Data type identifier
    :param version: Semantic version (MAJOR.MINOR.PATCH)
    :return: Schema for the specified version
    """
    try:
        schema = SchemaRegistryService.get_schema(db, data_type, version)
        if not schema:
            raise HTTPException(
                status_code=404,
                detail=f"No schema found for {data_type}:{version}",
            )
        return SchemaResponse(**schema)
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error fetching schema {data_type}:{version}: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Failed to fetch schema: {str(e)}")


@router.post("/schema/{data_type}", response_model=SchemaResponse, status_code=201)
async def register_schema(
    data_type: str,
    request: SchemaRegisterRequest = Body(...),
    user: Dict = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """
    Register a new schema version for a data type

    :param data_type: Data type identifier
    :param request: Schema registration request
    :return: Registered schema
    """
    try:
        # Validate compatibility mode
        valid_modes = ["BACKWARD", "FORWARD", "FULL", "NONE"]
        if request.compatibility_mode not in valid_modes:
            raise HTTPException(
                status_code=400,
                detail=f"Invalid compatibility_mode. Must be one of: {valid_modes}",
            )

        schema = SchemaRegistryService.register_schema(
            db=db,
            data_type=data_type,
            version=request.version,
            schema=request.schema_data,
            compatibility_mode=request.compatibility_mode,
        )
        return SchemaResponse(**schema)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        logger.error(
            f"Error registering schema {data_type}:{request.version}: {e}",
            exc_info=True,
        )
        raise HTTPException(
            status_code=500, detail=f"Failed to register schema: {str(e)}"
        )


@router.get("/schema/{data_type}/versions", response_model=SchemaVersionListResponse)
async def list_schema_versions(
    data_type: str,
    user: Dict = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """
    List all versions for a data type

    :param data_type: Data type identifier
    :return: List of all schema versions
    """
    try:
        versions = SchemaRegistryService.list_versions(db, data_type)
        return SchemaVersionListResponse(
            data_type=data_type,
            versions=[SchemaResponse(**v) for v in versions],
        )
    except Exception as e:
        logger.error(f"Error listing versions for {data_type}: {e}", exc_info=True)
        raise HTTPException(
            status_code=500, detail=f"Failed to list versions: {str(e)}"
        )


@router.post(
    "/schema/{data_type}/validate-compatibility",
    response_model=CompatibilityCheckResponse,
)
async def validate_compatibility(
    data_type: str,
    request: CompatibilityCheckRequest = Body(...),
    user: Dict = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """
    Check compatibility between two schemas

    Note: This is a simplified compatibility check. For full compatibility checking,
    use the Schema Registry's compatibility checker which validates against registered schemas.

    :param data_type: Data type identifier (for reference)
    :param request: Compatibility check request
    :return: Compatibility check result
    """
    try:
        # Validate compatibility mode
        valid_modes = ["BACKWARD", "FORWARD", "FULL", "NONE"]
        if request.mode not in valid_modes:
            raise HTTPException(
                status_code=400,
                detail=f"Invalid mode. Must be one of: {valid_modes}",
            )

        # For now, return a simple response
        # Full compatibility checking would require importing the CompatibilityChecker
        # which depends on the trading_server codebase
        return CompatibilityCheckResponse(
            compatible=True,
            message=(
                "Compatibility check not fully implemented in API layer. "
                "Use Schema Registry directly for full checking."
            ),
        )
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error checking compatibility: {e}", exc_info=True)
        raise HTTPException(
            status_code=500, detail=f"Failed to check compatibility: {str(e)}"
        )


@router.get("/data-docs/{data_type}")
async def get_data_docs(
    data_type: str,
    user: Dict = Depends(get_current_user),
):
    """
    Serve Great Expectations Data Docs for a data type

    :param data_type: Data type identifier
    :return: HTML response with Data Docs
    """
    try:
        # Try to find Data Docs in the project
        # Data Docs are typically in great_expectations/data_docs/local_site
        project_root = Path(__file__).parent.parent.parent.parent.parent
        data_docs_path = (
            project_root / "great_expectations" / "data_docs" / "local_site"
        )
        index_file = data_docs_path / "index.html"

        if index_file.exists():
            return FileResponse(
                str(index_file),
                media_type="text/html",
            )
        else:
            return HTMLResponse(
                content=f"""
                <html>
                    <head><title>Data Docs - {data_type}</title></head>
                    <body>
                        <h1>Data Docs for {data_type}</h1>
                        <p>Data Docs have not been generated yet. Run a validation to generate them.</p>
                    </body>
                </html>
                """,
                status_code=404,
            )
    except Exception as e:
        logger.error(f"Error serving Data Docs for {data_type}: {e}", exc_info=True)
        raise HTTPException(
            status_code=500, detail=f"Failed to serve Data Docs: {str(e)}"
        )


@router.get("/data-docs")
async def get_data_docs_index(user: Dict = Depends(get_current_user)):
    """
    Serve Great Expectations Data Docs index

    :return: HTML response with Data Docs index
    """
    try:
        project_root = Path(__file__).parent.parent.parent.parent.parent
        data_docs_path = (
            project_root / "great_expectations" / "data_docs" / "local_site"
        )
        index_file = data_docs_path / "index.html"

        if index_file.exists():
            return FileResponse(
                str(index_file),
                media_type="text/html",
            )
        else:
            return HTMLResponse(
                content="""
                <html>
                    <head><title>Data Docs</title></head>
                    <body>
                        <h1>Great Expectations Data Docs</h1>
                        <p>Data Docs have not been generated yet. Run a validation to generate them.</p>
                    </body>
                </html>
                """,
                status_code=404,
            )
    except Exception as e:
        logger.error(f"Error serving Data Docs index: {e}", exc_info=True)
        raise HTTPException(
            status_code=500, detail=f"Failed to serve Data Docs: {str(e)}"
        )
