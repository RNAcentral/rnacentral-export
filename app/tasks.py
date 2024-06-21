import asyncio
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
def fetch_data_from_search_index(self, api_url: str, data_type: str):
    self.update_state(state="SUBMITTED")  # set a custom initial state
    search_position = "0"  # initial search position
    ids = []
    hit_count = None
    ids_extracted = 0

    while True:
        response = requests.get(api_url + f"&searchposition={search_position}")
        if response.status_code == 200:
            data = response.json()
            if not hit_count:
                hit_count = data.get("hitCount")

            entries = data.get("entries", [])
            if not entries:
                break  # there is no more data to fetch

            ids.extend(entry["id"] for entry in entries)
            ids_extracted += len(entries)
            progress_ids = int((ids_extracted / hit_count) * 100)
            self.update_state(
                state="PROGRESS",
                meta={"progress_ids": progress_ids, "progress_db_data": 0}
            )
            search_position = data.get("searchPosition")  # next position
            if not search_position:
                break
        else:
            raise Exception("Failed to fetch data")

    if data_type == "ids":
        # save IDs to a compressed file
        ids_file_path = f"/srv/results/{self.request.id}.txt.gz"
        os.makedirs(os.path.dirname(ids_file_path), exist_ok=True)
        with gzip.open(ids_file_path, "wt", encoding="utf-8") as gz_file:
            gz_file.write("\n".join(ids))
        return {"ids_file_path": ids_file_path}

    elif data_type == "json":
        # fetch data from database in batches and write to a compressed file
        batch_size = 1000
        file_path = f"/srv/results/{self.request.id}.json.gz"
        os.makedirs(os.path.dirname(file_path), exist_ok=True)
        total_ids = len(ids)

        async def fetch_and_write():
            with gzip.open(file_path, "wt", encoding="utf-8") as gz_file:
                first = True
                for i in range(0, total_ids, batch_size):
                    batch_ids = ids[i:i + batch_size]
                    batch_data = await fetch_data_from_db(batch_ids)
                    if not first:
                        gz_file.write(", ")  # add comma between JSON objects
                    first = False
                    gz_file.write(json.dumps(batch_data, default=str))
                    progress_db_data = int((i + batch_size) / total_ids * 100)
                    self.update_state(
                        state="PROGRESS",
                        meta={
                            "progress_ids": 100,
                            "progress_db_data": progress_db_data
                        }
                    )
        asyncio.run(fetch_and_write())

        return file_path
