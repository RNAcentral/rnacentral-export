import gzip
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

    # fetch data from database in batches and write to a compressed file
    batch_size = 1000
    file_path = f"/srv/results/{self.request.id}.json.gz"
    os.makedirs(os.path.dirname(file_path), exist_ok=True)

    with gzip.open(file_path, "wt", encoding="utf-8") as gz_file:
        first = True
        for i in range(0, len(ids), batch_size):
            batch_ids = ids[i:i + batch_size]
            batch_data = fetch_data_from_db(batch_ids)
            if not first:
                gz_file.write(", ")  # add comma between JSON objects
            first = False
            json.dump(batch_data, gz_file, default=str)

    return file_path
