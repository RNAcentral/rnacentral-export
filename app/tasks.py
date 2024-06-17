import json
import os
import requests

from pydantic import BaseModel, ValidationError

from .celery import celery_app


class APIData(BaseModel):
    id: str
    source: str
    description: str


@celery_app.task(bind=True)
def fetch_data_from_search_index(self, api_url: str):
    # set a custom initial state to help validate the existence of a task_id
    self.update_state(state="SUBMITTED")
    response = requests.get(api_url)
    if response.status_code == 200:
        try:
            data = response.json()
            extracted_ids = [entry["id"] for entry in data["entries"]]
            file_path = save_ids_to_file(extracted_ids, self.request.id)
            return file_path
        except (ValidationError, KeyError) as e:
            raise Exception(f"Error processing data: {e}")
    else:
        raise Exception("Failed to fetch data")


def save_ids_to_file(ids, task_id):
    file_path = f"/srv/results/{task_id}.json"
    os.makedirs(os.path.dirname(file_path), exist_ok=True)
    with open(file_path, "w") as f:
        json.dump(ids, f)
    return file_path
