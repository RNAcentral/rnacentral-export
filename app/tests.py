import pytest

from fastapi.testclient import TestClient
from unittest.mock import Mock

from .main import app
from .tasks import fetch_data_from_search_index

client = TestClient(app)


@pytest.fixture
def mock_fetch_data(mocker):
    mock_task = Mock()
    mock_task.id = "mock-task-id"
    mocker.patch.object(
        fetch_data_from_search_index,
        "delay",
        return_value=mock_task
    )
    return mock_task


def test_fetch_data_with_fasta(mock_fetch_data):
    api = ("https://wwwdev.ebi.ac.uk/ebisearch/ws/rest/rnacentral?"
           "query=(TAXONOMY:559292)&size=1&sort=id&format=json")
    response = client.post(
        "/fetch-data/",
        json={"api_url": api, "data_type": "fasta"}
    )
    assert response.status_code == 200
    assert response.json() == {
        "task_id": "mock-task-id",
        "data_type": "fasta"
    }


def test_fetch_data_with_ids(mock_fetch_data):
    api = ("https://wwwdev.ebi.ac.uk/ebisearch/ws/rest/rnacentral?"
           "query=(TAXONOMY:559292)&size=1&sort=id&format=json")
    response = client.post(
        "/fetch-data/",
        json={"api_url": api, "data_type": "ids"}
    )
    assert response.status_code == 200
    assert response.json() == {
        "task_id": "mock-task-id",
        "data_type": "ids"
    }


def test_fetch_data_with_json(mock_fetch_data):
    api = ("https://wwwdev.ebi.ac.uk/ebisearch/ws/rest/rnacentral?"
           "query=(TAXONOMY:559292)&size=1&sort=id&format=json")
    response = client.post(
        "/fetch-data/",
        json={"api_url": api, "data_type": "json"}
    )
    assert response.status_code == 200
    assert response.json() == {
        "task_id": "mock-task-id",
        "data_type": "json"
    }


def test_fetch_data_with_invalid_data_type(mock_fetch_data):
    api = ("https://wwwdev.ebi.ac.uk/ebisearch/ws/rest/rnacentral?"
           "query=(TAXONOMY:559292)&size=1&sort=id&format=json")
    response = client.post(
        "/fetch-data/",
        json={"api_url": api, "data_type": "invalid"}
    )
    assert response.status_code == 422


def test_fetch_data_with_empty_url(mock_fetch_data):
    response = client.post(
        "/fetch-data/",
        json={"api_url": "", "data_type": "json"}
    )
    assert response.status_code == 422


def test_download_file_pending(mocker):
    mocker.patch.object(
        fetch_data_from_search_index,
        "AsyncResult",
        return_value=Mock(state="PENDING")
    )
    response = client.get("/download/mock-task-id/json")
    assert response.status_code == 404
    assert response.json() == {"detail": "Task ID not found"}


def test_download_file_not_found(mocker):
    mocker.patch.object(
        fetch_data_from_search_index,
        "AsyncResult",
        return_value=Mock(state="SUCCESS")
    )
    mocker.patch("os.path.exists", return_value=False)
    response = client.get("/download/mock-task-id/json")
    assert response.status_code == 404
    assert response.json() == {"detail": "File not found"}


def test_download_file_failure(mocker):
    mocker.patch.object(
        fetch_data_from_search_index,
        "AsyncResult",
        return_value=Mock(state="FAILURE")
    )
    response = client.get("/download/mock-task-id/json")
    assert response.status_code == 500
    assert response.json() == {"detail": "Task failed"}


def test_download_file_revoked(mocker):
    mocker.patch.object(
        fetch_data_from_search_index,
        "AsyncResult",
        return_value=Mock(state="REVOKED")
    )
    response = client.get("/download/mock-task-id/json")
    assert response.status_code == 400
    assert response.json() == {"detail": "Task was revoked"}


def test_download_file_retry(mocker):
    mocker.patch.object(
        fetch_data_from_search_index,
        "AsyncResult",
        return_value=Mock(state="RETRY")
    )
    response = client.get("/download/mock-task-id/json")
    assert response.status_code == 500
    assert response.json() == {"detail": "Task is being retried"}


def test_download_file_processing(mocker):
    mocker.patch.object(
        fetch_data_from_search_index,
        "AsyncResult",
        return_value=Mock(state="STARTED")
    )
    response = client.get("/download/mock-task-id/json")
    assert response.status_code == 202
    assert response.json() == {"detail": "Task is still processing"}


def test_download_file_progress(mocker):
    mock_result = Mock(state="RUNNING")
    mock_result.info = {"progress_ids": 50, "progress_db_data": 0}
    mocker.patch.object(
        fetch_data_from_search_index,
        "AsyncResult",
        return_value=mock_result
    )
    response = client.get("/download/mock-task-id/json")
    assert response.status_code == 200
    assert response.json() == {
        "task_id": "mock-task-id",
        "state": "RUNNING",
        "progress_ids": 50,
        "progress_db_data": 0
    }
