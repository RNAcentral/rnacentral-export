import json
import os
import requests

from pydantic import BaseModel

from .celery import celery_app
from .database import fetch_data_from_db


class APIData(BaseModel):
    id: str
    source: str
    description: str


@celery_app.task(bind=True)
def fetch_data_from_search_index(self, api_url: str):
    self.update_state(state="SUBMITTED")  # set a custom initial state
    search_position = "0"  # initial search position
    ids = []

    while True:
        response = requests.get(api_url + f"&searchposition={search_position}")
        if response.status_code == 200:
            data = response.json()
            entries = data.get("entries", [])
            if not entries:
                break  # there is no more data to fetch
            ids.extend(entry["id"] for entry in entries)
            search_position = data.get("searchPosition")  # next position
            if not search_position:
                break
        else:
            raise Exception("Failed to fetch data")

    # fetch data from database in batches
    batch_size = 1000
    db_data = []
    for i in range(0, len(ids), batch_size):
        batch_ids = ids[i:i + batch_size]
        batch_data = fetch_data_from_db(batch_ids)
        db_data.extend(batch_data)

    # save the data to a file
    file_path = f"/srv/results/{self.request.id}.json"
    os.makedirs(os.path.dirname(file_path), exist_ok=True)
    with open(file_path, "w") as file:
        json.dump(db_data, file, default=str)

    return file_path
