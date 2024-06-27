import asyncio
import gzip
import json
import os
import requests
import subprocess as sub

from pydantic import BaseModel

from .celery import celery_app
from .config import get_settings
from .database import fetch_data_from_db
from .logger import logger


class APIData(BaseModel):
    id: str
    source: str
    description: str


@celery_app.task(bind=True)
def fetch_data_from_search_index(self, api_url: str, data_type: str):
    settings = get_settings()
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

            # extract ids
            ids.extend(entry["id"] for entry in entries)
            ids_extracted += len(entries)
            progress_ids = min(round(ids_extracted * 100 / hit_count), 95)

            # update progress bar
            if data_type == "json":
                self.update_state(
                    state="PROGRESS",
                    meta={"progress_ids": progress_ids, "progress_db_data": 0}
                )
            elif data_type == "fasta":
                self.update_state(
                    state="PROGRESS",
                    meta={"progress_ids": progress_ids, "progress_fasta": 0}
                )
            else:
                self.update_state(
                    state="PROGRESS",
                    meta={"progress_ids": progress_ids}
                )

            search_position = data.get("searchPosition")  # next position
            if not search_position:
                break
        else:
            raise Exception("Failed to fetch data")

    # check for duplicate IDs
    if len(ids) != len(set(ids)):
        ids = list(set(ids))
        logger.info(f"There are duplicate IDs at this URL: {api_url}")

    if data_type == "ids":
        # save IDs to a compressed file
        ids_file_path = f"/srv/results/{self.request.id}.txt.gz"
        os.makedirs(os.path.dirname(ids_file_path), exist_ok=True)
        with gzip.open(ids_file_path, "wt", encoding="utf-8") as gz_file:
            gz_file.write("\n".join(ids))
        self.update_state(state="PROGRESS", meta={"progress_ids": 100})
        return {"ids_file_path": ids_file_path}

    elif data_type == "json":
        # fetch data from database in batches and write to a compressed file
        batch_size = 1000
        file_path = f"/srv/results/{self.request.id}.json.gz"
        os.makedirs(os.path.dirname(file_path), exist_ok=True)
        total_ids = len(ids)
        self.update_state(
            state="PROGRESS",
            meta={"progress_ids": 100, "progress_db_data": 0}
        )

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

        # create a new event loop for this task
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        try:
            loop.run_until_complete(fetch_and_write())
        finally:
            loop.close()

        return file_path

    if data_type == "fasta":
        # generate FASTA file using esl-sfetch
        temp_ids_file = f"/srv/results/{self.request.id}.txt"
        fasta_file_path = f"/srv/results/{self.request.id}.fasta.gz"
        self.update_state(
            state="PROGRESS",
            meta={"progress_ids": 100, "progress_fasta": 0}
        )

        with open(temp_ids_file, "w") as ids_file:
            ids_file.write("\n".join(ids))

        self.update_state(
            state="PROGRESS",
            meta={"progress_ids": 100, "progress_fasta": 50}
        )

        cmd = "{esl_binary} -f {fasta} {id_list} | gzip > {output}".format(
            esl_binary=settings.esl_binary,
            fasta=settings.fasta,
            id_list=temp_ids_file,
            output=fasta_file_path,
        )

        try:
            process = sub.run(cmd, shell=True, check=True, capture_output=True)
            if process.stderr:
                raise sub.CalledProcessError(
                    process.returncode,
                    cmd,
                    output=process.stdout,
                    stderr=process.stderr
                )
            self.update_state(
                state="PROGRESS",
                meta={"progress_ids": 100, "progress_fasta": 100}
            )
        except sub.CalledProcessError as e:
            logger.error(f"esl-sfetch failed: {e.stderr.decode('utf-8')}")
            self.update_state(
                state="FAILURE",
                meta={"exc_type": type(e).__name__, "exc_message": str(e)}
            )
            raise

        os.remove(temp_ids_file)
        return {"fasta_file": fasta_file_path}
