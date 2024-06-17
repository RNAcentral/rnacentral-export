import os

from fastapi import BackgroundTasks, FastAPI, HTTPException
from fastapi.responses import FileResponse
from pydantic import BaseModel, Field

from .logger import logger
from .tasks import fetch_data_from_search_index


class APIRequest(BaseModel):
    api_url: str = Field(..., example="https://wwwdev.ebi.ac.uk/ebisearch/ws/rest/rnacentral?query=(so_rna_type_name:NcRNA)&fields=description&size=1000&format=json")


app = FastAPI(docs_url="/")


@app.post("/fetch-data/")
def fetch_data(request: APIRequest):
    task = fetch_data_from_search_index.delay(request.api_url)
    logger.info(f"Data export started for URL: {request.api_url}")
    return {
        "message": "Data fetch initiated, check Celery for the status.",
        "task_id": task.id
    }


@app.get("/download/{task_id}")
def download_file(task_id: str):
    result = fetch_data_from_search_index.AsyncResult(task_id)
    if result.state == "PENDING":
        # a valid task_id will never be PENDING, as we are changing the initial
        # status to SUBMITTED
        logger.info(f"Task ID not found: {task_id}")
        raise HTTPException(status_code=404, detail="Task ID not found")
    elif result.state == "SUCCESS":
        file_path = f"/srv/results/{task_id}.json"
        if os.path.exists(file_path):
            logger.info(f"Showing results for Task ID: {task_id}")
            return FileResponse(
                path=file_path,
                filename=f"{task_id}.json",
                media_type="application/json"
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
