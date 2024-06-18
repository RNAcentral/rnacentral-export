import pytest
from fastapi.testclient import TestClient

from .main import app
from .tasks import fetch_data_from_search_index

client = TestClient(app)


@pytest.fixture
def mock_fetch_data(mocker):
    mock_task = mocker.Mock()
    mock_task.id = "mock-task-id"
    mocker.patch.object(
        fetch_data_from_search_index,
        "delay",
        return_value=mock_task
    )
    return mock_task


def test_fetch_data(mock_fetch_data):
    api = ("https://wwwdev.ebi.ac.uk/ebisearch/ws/rest/rnacentral?"
           "query=(TAXONOMY:9606)&size=1&sort=id&format=json")
    response = client.post("/fetch-data/", json={"api_url": api})
    assert response.status_code == 200
    assert response.json() == {
        "message": "Data fetch initiated, check Celery for the status.",
        "task_id": "mock-task-id"
    }


def test_download_file_pending(mocker):
    mocker.patch.object(
        fetch_data_from_search_index,
        "AsyncResult",
        return_value=mocker.Mock(state="PENDING")
    )
    response = client.get("/download/mock-task-id")
    assert response.status_code == 404
    assert response.json() == {"detail": "Task ID not found"}


def test_download_file_not_found(mocker):
    mocker.patch.object(
        fetch_data_from_search_index,
        "AsyncResult",
        return_value=mocker.Mock(state="SUCCESS")
    )
    mocker.patch("os.path.exists", return_value=False)
    response = client.get("/download/mock-task-id")
    assert response.status_code == 404
    assert response.json() == {"detail": "File not found"}


def test_download_file_failure(mocker):
    mocker.patch.object(
        fetch_data_from_search_index,
        "AsyncResult",
        return_value=mocker.Mock(state="FAILURE")
    )
    response = client.get("/download/mock-task-id")
    assert response.status_code == 500
    assert response.json() == {"detail": "Task failed"}


def test_download_file_revoked(mocker):
    mocker.patch.object(
        fetch_data_from_search_index,
        "AsyncResult",
        return_value=mocker.Mock(state="REVOKED")
    )
    response = client.get("/download/mock-task-id")
    assert response.status_code == 400
    assert response.json() == {"detail": "Task was revoked"}


def test_download_file_retry(mocker):
    mocker.patch.object(
        fetch_data_from_search_index,
        "AsyncResult",
        return_value=mocker.Mock(state="RETRY")
    )
    response = client.get("/download/mock-task-id")
    assert response.status_code == 500
    assert response.json() == {"detail": "Task is being retried"}


def test_download_file_processing(mocker):
    mocker.patch.object(
        fetch_data_from_search_index,
        "AsyncResult",
        return_value=mocker.Mock(state="STARTED")
    )
    response = client.get("/download/mock-task-id")
    assert response.status_code == 202
    assert response.json() == {"detail": "Task is still processing"}
