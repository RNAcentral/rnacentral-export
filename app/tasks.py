import datetime
import gzip
import json
import os
import requests
import subprocess as sub
import time

from urllib.parse import urlparse, parse_qs

from .celery import celery_app
from .config import get_settings
from .database import fetch_data_from_db
from .logger import logger


def get_response_or_retry(url: str, max_retries: int = 3) -> requests.Response:
    """
    If the request fails (i.e., the status code is not 200), wait for a short
    period before retrying. If all attempts fail, raise an exception.
    """
    attempts = 0
    while attempts < max_retries:
        try:
            response = requests.get(url)
            if response.status_code == 200:
                return response
            else:
                logger.error(f"Failed to fetch data from {url} with status code {response.status_code}")
                attempts += 1
                if attempts < max_retries:
                    time.sleep(5)
                else:
                    logger.error(f"Failed to fetch data from {url} after {max_retries} attempts")
                    raise Exception("Failed to fetch data from Search Index")
        except requests.RequestException as e:
            logger.error(f"Exception occurred while fetching data from {url}: {e}")
            attempts += 1
            if attempts < max_retries:
                time.sleep(5)
            else:
                logger.error(f"Failed to fetch data from {url} after {max_retries} attempts")
                raise


@celery_app.task(bind=True)
def fetch_data_from_search_index(self, api_url: str, data_type: str):
    settings = get_settings()
    self.update_state(state="SUBMITTED")  # set a custom initial state
    search_position = "0"  # initial search position
    ids = []
    hit_count = None
    ids_extracted = 0
    query_params = parse_qs(urlparse(api_url).query)  # extract query params
    query = query_params.get("query", [None])[0]  # get query

    while True:
        response = get_response_or_retry(
            api_url + f"&searchposition={search_position}"
        )
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
                state="RUNNING",
                meta={
                    "query": query,
                    "hit_count": hit_count,
                    "progress_ids": progress_ids,
                    "progress_db_data": 0
                }
            )
        elif data_type == "fasta":
            self.update_state(
                state="RUNNING",
                meta={
                    "query": query,
                    "hit_count": hit_count,
                    "progress_ids": progress_ids,
                    "progress_fasta": 0
                }
            )
        else:
            self.update_state(
                state="RUNNING",
                meta={
                    "query": query,
                    "hit_count": hit_count,
                    "progress_ids": progress_ids
                }
            )

        search_position = data.get("searchPosition")  # next position
        if not search_position:
            break

    # check for duplicate IDs
    if len(ids) != len(set(ids)):
        ids = list(set(ids))
        logger.info(f"There are duplicate IDs at this URL: {api_url}")

    if data_type == "txt":
        # save IDs to a compressed file
        ids_file_path = f"/srv/results/{self.request.id}.txt.gz"
        os.makedirs(os.path.dirname(ids_file_path), exist_ok=True)
        with gzip.open(ids_file_path, "wt", encoding="utf-8") as gz_file:
            gz_file.write("\n".join(ids))
        self.update_state(
            state="RUNNING",
            meta={"query": query, "hit_count": hit_count, "progress_ids": 100}
        )
        logger.info(f"Data export finished for: {self.request.id}")
        return {"ids_file_path": ids_file_path}

    elif data_type == "json":
        # fetch data from database in batches and write to a compressed file
        batch_size = 1000
        file_path = f"/srv/results/{self.request.id}.json.gz"
        os.makedirs(os.path.dirname(file_path), exist_ok=True)
        total_ids = len(ids)
        self.update_state(
            state="RUNNING",
            meta={
                "query": query,
                "hit_count": hit_count,
                "progress_ids": 100,
                "progress_db_data": 0
            }
        )

        with gzip.open(file_path, "wt", encoding="utf-8") as gz_file:
            date_time = datetime.datetime.now().strftime("%d %B %Y %H:%M:%S")

            # add some metadata
            gz_file.write('{"job": "')
            gz_file.write(self.request.id)
            gz_file.write('", "rnacentral_version": "v24", ')
            gz_file.write(
                '"licenses": [{"name": "CC0", "path": '
                '"https://creativecommons.org/share-your-work/public-domain'
                '/cc0/", "title": "Creative Commons Zero license"}], '
            )
            gz_file.write(f'"download_date": "{date_time}", ')
            gz_file.write('"results": [')

            first = True
            for i in range(0, total_ids, batch_size):
                batch_ids = ids[i:i + batch_size]
                batch_data = fetch_data_from_db(batch_ids)
                for entry in batch_data:
                    if not first:
                        gz_file.write(", ")  # add comma between JSON objects
                    first = False
                    gz_file.write(json.dumps(entry, default=str))
                progress_db_data = int((i + batch_size) / total_ids * 100)
                self.update_state(
                    state="RUNNING",
                    meta={
                        "query": query,
                        "hit_count": hit_count,
                        "progress_ids": 100,
                        "progress_db_data": progress_db_data
                    }
                )
            gz_file.write("]}")

        logger.info(f"Data export finished for: {self.request.id}")
        return file_path

    if data_type == "fasta":
        # generate FASTA file using esl-sfetch
        temp_ids_file = f"/srv/results/{self.request.id}.txt"
        fasta_file_path = f"/srv/results/{self.request.id}.fasta.gz"
        self.update_state(
            state="RUNNING",
            meta={
                "query": query,
                "hit_count": hit_count,
                "progress_ids": 100,
                "progress_fasta": 0
            }
        )

        with open(temp_ids_file, "w") as ids_file:
            ids_file.write("\n".join(ids))

        self.update_state(
            state="RUNNING",
            meta={
                "query": query,
                "hit_count": hit_count,
                "progress_ids": 100,
                "progress_fasta": 50
            }
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
                state="RUNNING",
                meta={
                    "query": query,
                    "hit_count": hit_count,
                    "progress_ids": 100,
                    "progress_fasta": 100
                }
            )
        except sub.CalledProcessError as e:
            logger.error(f"esl-sfetch failed: {e.stderr.decode('utf-8')}")
            self.update_state(
                state="FAILURE",
                meta={"exc_type": type(e).__name__, "exc_message": str(e)}
            )
            raise

        os.remove(temp_ids_file)
        logger.info(f"Data export finished for: {self.request.id}")
        return {"fasta_file": fasta_file_path}
