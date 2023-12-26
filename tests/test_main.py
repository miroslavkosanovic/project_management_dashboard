from fastapi.testclient import TestClient
from main.main import app

client = TestClient(app)


def test_create_project():
    response = client.post("/projects", json={"name": "Test Project"})
    assert response.status_code == 200
    assert response.json() == {
        "project_id": "1",
        "project": {
            "name": "Test Project",
            "details": None,
            "documents": [],
            "logo": None,
        },
    }


def test_get_all_projects():
    response = client.get("/projects")
    assert response.status_code == 200
    assert response.json() == {
        "1": {"name": "Test Project", "details": None, "documents": [], "logo": None}
    }


def test_get_project_info():
    response = client.get("/project/1/info")
    assert response.status_code == 200
    assert response.json() == {"project_id": "1", "name": "Test Project"}


def test_update_project_info():
    response = client.put("/project/1/info", json={"name": "Updated Project"})
    assert response.status_code == 200
    assert response.json() == {"project_id": "1", "name": "Updated Project"}


def test_delete_project():
    response = client.delete("/project/1")
    assert response.status_code == 200
    assert response.json() == {"message": "Project deleted"}
