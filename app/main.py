import os

from fastapi import FastAPI, HTTPException
from fastapi.responses import FileResponse, JSONResponse
from pydantic import AnyHttpUrl, BaseModel, Field, field_validator, TypeAdapter
from typing import Literal

from .logger import logger
from .tasks import fetch_data_from_search_index


class APIRequest(BaseModel):
    api_url: str = Field(..., json_schema_extra={"example": "https://www.ebi.ac.uk/ebisearch/ws/rest/rnacentral?query=(TAXONOMY:9606)&size=500&sort=id&format=json"})
    data_type: Literal["fasta", "ids", "json"]

    @field_validator("api_url")
    def validate_api_url(cls, url):
        TypeAdapter(AnyHttpUrl).validate_python(url)
        return url


app = FastAPI(docs_url="/")


@app.post("/fetch-data/")
def fetch_data(request: APIRequest):
    task = fetch_data_from_search_index.delay(
        request.api_url,
        request.data_type
    )
    logger.info(
        f"Data export started for URL: {request.api_url} "
        f"with data type: {request.data_type}"
    )
    return {"task_id": task.id, "data_type": request.data_type}


@app.get("/download/{task_id}/fasta")
def download_fasta(task_id: str):
    return download_file(task_id, "fasta")


@app.get("/download/{task_id}/ids")
def download_ids(task_id: str):
    return download_file(task_id, "ids")


@app.get("/download/{task_id}/json")
def download_json(task_id: str):
    return download_file(task_id, "json")


def download_file(task_id: str, data_type: str):
    result = fetch_data_from_search_index.AsyncResult(task_id)
    if result.state == "PENDING":
        # a valid task_id will never be PENDING, as we are changing the initial
        # status to SUBMITTED
        logger.info(f"Task ID not found: {task_id}")
        raise HTTPException(status_code=404, detail="Task ID not found")

    elif result.state == "PROGRESS":
        progress_ids = result.info.get("progress_ids", 0)
        content = {
            "task_id": task_id,
            "state": result.state,
            "progress_ids": progress_ids,
        }
        if data_type == "json":
            content["progress_db_data"] = result.info.get("progress_db_data", 0)
        return JSONResponse(content=content)

    elif result.state == "SUCCESS":
        if data_type == "json":
            file_extension = "json.gz"
        elif data_type == "fasta":
            file_extension = "fasta.gz"
        else:
            file_extension = "txt.gz"
        file_path = f"/srv/results/{task_id}.{file_extension}"
        if os.path.exists(file_path):
            logger.info(f"Showing results for Task ID: {task_id}")
            return FileResponse(
                path=file_path,
                filename=f"{task_id}.{file_extension}",
                media_type="application/gzip",
                headers={"Content-Disposition": f"attachment; filename={task_id}.{file_extension}"}
            )
        else:
            logger.error(f"Results file could not be found: {task_id}")
            raise HTTPException(status_code=404, detail="File not found")

    elif result.state == "FAILURE":
        logger.error(f"Task ID failed: {task_id}")
        raise HTTPException(status_code=500, detail="Task failed")

    elif result.state == "REVOKED":
        logger.error(f"Task ID revoked: {task_id}")
        raise HTTPException(status_code=400, detail="Task was revoked")

    elif result.state == "RETRY":
        logger.error(f"Task ID is being retried: {task_id}")
        raise HTTPException(status_code=500, detail="Task is being retried")

    else:
        raise HTTPException(status_code=202, detail="Task is still processing")
