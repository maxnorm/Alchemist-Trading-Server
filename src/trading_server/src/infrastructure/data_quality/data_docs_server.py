"""
Data Docs Server - Serve Great Expectations Data Docs via FastAPI
"""

import logging
from fastapi import APIRouter, HTTPException
from fastapi.responses import FileResponse, HTMLResponse

from .ge_context import get_ge_context

logger = logging.getLogger(__name__)

router = APIRouter()


@router.get("/data-docs/{data_type}")
async def get_data_docs(data_type: str):
    """
    Serve Great Expectations Data Docs for a data type

    :param data_type: Data type identifier
    :return: HTML response with Data Docs
    """
    try:
        ge_context = get_ge_context()
        data_docs_path = ge_context.get_data_docs_path()

        # Look for index.html in data_docs
        index_file = data_docs_path / "index.html"

        if index_file.exists():
            return FileResponse(
                str(index_file),
                media_type="text/html",
            )
        else:
            # Return a simple message if Data Docs not generated yet
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
async def get_data_docs_index():
    """
    Serve Great Expectations Data Docs index

    :return: HTML response with Data Docs index
    """
    try:
        ge_context = get_ge_context()
        data_docs_path = ge_context.get_data_docs_path()
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
