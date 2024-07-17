import aiofiles
import os

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse, StreamingResponse
from pydantic import AnyHttpUrl, BaseModel, Field, field_validator, TypeAdapter
from typing import Literal

from .logger import logger
from .tasks import fetch_data_from_search_index


app = FastAPI(docs_url="/")

origins = [
    "http://localhost",
    "http://127.0.0.1",
    "https://test.rnacentral.org",
    "https://rnacentral.org",
    "https://export.rnacentral.org",
]

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


class APIRequest(BaseModel):
    api_url: str = Field(..., json_schema_extra={"example": "https://www.ebi.ac.uk/ebisearch/ws/rest/rnacentral?query=(TAXONOMY:9606)&size=1000&sort=id&format=json"})
    data_type: Literal["fasta", "json", "txt"]

    @field_validator("api_url")
    def validate_api_url(cls, url):
        TypeAdapter(AnyHttpUrl).validate_python(url)
        return url


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
async def download_fasta(task_id: str):
    return await download_file(task_id, "fasta")


@app.get("/download/{task_id}/txt")
async def download_txt(task_id: str):
    return await download_file(task_id, "txt")


@app.get("/download/{task_id}/json")
async def download_json(task_id: str):
    return await download_file(task_id, "json")


async def download_file(task_id: str, data_type: str):
    result = fetch_data_from_search_index.AsyncResult(task_id)
    if result.state == "PENDING":
        # a valid task_id will never be PENDING, as we are changing the initial
        # status to SUBMITTED
        logger.info(f"Task ID not found: {task_id}")
        raise HTTPException(status_code=404, detail="Task ID not found")

    elif result.state == "RUNNING":
        hit_count = result.info.get("hit_count", 0)
        progress_ids = result.info.get("progress_ids", 0)
        content = {
            "task_id": task_id,
            "hit_count": hit_count,
            "state": result.state,
            "progress_ids": progress_ids,
        }
        if data_type == "json":
            content["progress_db_data"] = result.info.get("progress_db_data", 0)
        elif data_type == "fasta":
            content["progress_fasta"] = result.info.get("progress_fasta", 0)
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
            return await stream_file(file_path, f"{task_id}.{file_extension}")
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


async def stream_file(file_path: str, filename: str):
    async def read_file():
        async with aiofiles.open(file_path, "rb") as file:
            while chunk := await file.read(16384):  # Read in 16MB chunks
                yield chunk

    file_size = os.path.getsize(file_path)

    return StreamingResponse(
        read_file(),
        media_type="application/gzip",
        headers={
            "Content-Disposition": f"attachment; filename={filename}",
            "Content-Length": str(file_size)
        }
    )
