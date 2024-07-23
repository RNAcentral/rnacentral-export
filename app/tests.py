import pytest

from fastapi.testclient import TestClient
from unittest.mock import Mock

from .main import app
from .tasks import fetch_data_from_search_index

client = TestClient(app)


@pytest.fixture
def mock_data(mocker):
    mock_task = Mock()
    mock_task.id = "mock-task-id"
    mocker.patch.object(
        fetch_data_from_search_index,
        "delay",
        return_value=mock_task
    )
    return mock_task


def test_submit_data_with_fasta(mock_data):
    api = ("https://wwwdev.ebi.ac.uk/ebisearch/ws/rest/rnacentral?"
           "query=(TAXONOMY:559292)&size=1&sort=id&format=json")
    response = client.post(
        "/submit/",
        json={"api_url": api, "data_type": "fasta"}
    )
    assert response.status_code == 200
    assert response.json() == {
        "task_id": "mock-task-id",
        "data_type": "fasta"
    }


def test_submit_data_with_txt(mock_data):
    api = ("https://wwwdev.ebi.ac.uk/ebisearch/ws/rest/rnacentral?"
           "query=(TAXONOMY:559292)&size=1&sort=id&format=json")
    response = client.post(
        "/submit/",
        json={"api_url": api, "data_type": "txt"}
    )
    assert response.status_code == 200
    assert response.json() == {
        "task_id": "mock-task-id",
        "data_type": "txt"
    }


def test_submit_data_with_json(mock_data):
    api = ("https://wwwdev.ebi.ac.uk/ebisearch/ws/rest/rnacentral?"
           "query=(TAXONOMY:559292)&size=1&sort=id&format=json")
    response = client.post(
        "/submit/",
        json={"api_url": api, "data_type": "json"}
    )
    assert response.status_code == 200
    assert response.json() == {
        "task_id": "mock-task-id",
        "data_type": "json"
    }


def test_submit_data_with_invalid_data_type(mock_data):
    api = ("https://wwwdev.ebi.ac.uk/ebisearch/ws/rest/rnacentral?"
           "query=(TAXONOMY:559292)&size=1&sort=id&format=json")
    response = client.post(
        "/submit/",
        json={"api_url": api, "data_type": "invalid"}
    )
    assert response.status_code == 422


def test_submit_data_with_empty_url(mock_data):
    response = client.post(
        "/submit/",
        json={"api_url": "", "data_type": "json"}
    )
    assert response.status_code == 422


def test_get_task_info_success(mocker):
    mock_result = Mock(state="SUCCESS")
    mock_result.result = {
        "query": "test_query",
        "data_type": "json",
        "hit_count": 100,
        "progress_ids": 100,
        "progress_db_data": 100
    }
    mocker.patch.object(
        fetch_data_from_search_index,
        "AsyncResult",
        return_value=mock_result
    )
    response = client.get("/status/mock-task-id")
    assert response.status_code == 200
    assert response.json() == {
        "task_id": "mock-task-id",
        "state": "SUCCESS",
        "query": "test_query",
        "data_type": "json",
        "hit_count": 100,
        "progress_ids": 100,
        "progress_db_data": 100
    }


def test_get_task_info_running(mocker):
    mock_result = Mock(state="RUNNING")
    mock_result.info = {
        "query": "test_query",
        "data_type": "fasta",
        "hit_count": 200,
        "progress_ids": 50,
        "progress_fasta": 25
    }
    mocker.patch.object(
        fetch_data_from_search_index,
        "AsyncResult",
        return_value=mock_result
    )
    response = client.get("/status/mock-task-id")
    assert response.status_code == 200
    assert response.json() == {
        "task_id": "mock-task-id",
        "state": "RUNNING",
        "query": "test_query",
        "data_type": "fasta",
        "hit_count": 200,
        "progress_ids": 50,
        "progress_fasta": 25
    }


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
    mock_result.info = {
        "query": "",
        "hit_count": 200,
        "progress_ids": 50,
        "progress_db_data": 0
    }
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
        "query": "",
        "hit_count": 200,
        "progress_ids": 50,
        "progress_db_data": 0
    }


def test_stream_file_success(mocker):
    file_path = "/srv/results/mock-task-id.json.gz"
    filename = "mock-task-id.json.gz"
    file_size = 1024

    mocker.patch("os.path.exists", return_value=True)
    mocker.patch("os.path.getsize", return_value=file_size)
    mock_open = mocker.patch("builtins.open", mocker.mock_open(read_data=b"data"))

    mock_result = Mock()
    mock_result.state = "SUCCESS"
    mock_result.info = {}
    mocker.patch.object(
        fetch_data_from_search_index,
        "AsyncResult",
        return_value=mock_result
    )

    response = client.get("/download/mock-task-id/json")

    assert response.status_code == 200
    assert response.headers["Content-Disposition"] == f"attachment; filename={filename}"
    assert response.headers["Content-Length"] == str(file_size)
    mock_open.assert_called_once_with(file_path, "rb")
