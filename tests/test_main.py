from fastapi.testclient import TestClient
from main.main import app

client = TestClient(app)


def test_create_project():
    response = client.post(
        "/projects",
        json={"name": "Test Project", "description": "This is a test project"},
    )
    assert response.status_code == 200
    assert response.json() == {
        "project_id": "1",
        "project": {"name": "Test Project", "description": "This is a test project"},
    }


def test_get_all_projects():
    response = client.get("/projects")
    assert response.status_code == 200
    assert response.json() == {
        "1": {"name": "Test Project", "description": "This is a test project"}
    }


def test_get_project_info():
    response = client.get("/project/1/info")
    assert response.status_code == 200
    assert response.json() == {
        "name": "Test Project",
        "description": "This is a test project",
    }


def test_update_project_info():
    response = client.put(
        "/project/1/info",
        json={
            "name": "Updated Project",
            "description": "This is an updated test project",
        },
    )
    assert response.status_code == 200
    assert response.json() == {
        "project_id": "1",
        "project": {
            "name": "Updated Project",
            "description": "This is an updated test project",
        },
    }


def test_delete_project():
    response = client.delete("/project/1")
    assert response.status_code == 200
    assert response.json() == {"message": "Project deleted"}
