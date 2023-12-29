from fastapi.testclient import TestClient
from main.main import app

client = TestClient(app)


def test_create_project():
    response = client.post("/projects", json={"name": "Test Project"})
    assert response.status_code == 200
    assert response.json() == {
        "project_id": 1,
        "project": {
            "name": "Test Project",
            "details": None,
            "documents": [],
            "logo": None,
        },
    }

def test_create_user():
    response = client.post("/auth", json={"name": "test", "email": "test@test.com", "password": "test", "role": "test"})
    assert response.status_code == 200

def test_get_all_projects():
    # Authenticate
    login_response = client.post("/login", json={"email": "test@test.com", "password": "test"})
    assert login_response.status_code == 200
    token = login_response.json()["access_token"]

    # Make the request to the /projects endpoint
    response = client.get("/projects", headers={"Authorization": f"Bearer {token}"})

    assert response.status_code == 200
    assert response.json() == [
        {
            "id": 1,
            "name": "Test Project",
            "details": None,
            "documents": "{}",
            "logo": None,
        }
    ]


def test_get_project_info():
    response = client.get("/project/1/info")
    assert response.status_code == 200
    assert response.json() == {
        "project_id": 1,
        "name": "Test Project",
        "details": None,
        "documents": "{}",
        "logo": None,
    }


def test_update_project_info():
    response = client.put("/project/1/info", json={"name": "Updated Project"})
    assert response.status_code == 200
    assert response.json() == {
        "project_id": 1,
        "name": "Updated Project",
        "details": None,
        "documents": "{}",
        "logo": None,
    }


def test_delete_project():
    response = client.delete("/project/1")
    assert response.status_code == 200
    assert response.json() == {"message": "Project deleted"}
