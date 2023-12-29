from fastapi.testclient import TestClient
from main.main import app, get_db, User, Project
from werkzeug.security import generate_password_hash
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
import os
import pytest
from sqlalchemy import text

client = TestClient(app)


@pytest.fixture(autouse=True)
def clear_database():
    with db() as session:
        session.execute(text("TRUNCATE TABLE projects RESTART IDENTITY CASCADE"))
        session.commit()


db_user = os.getenv("DB_USER")
db_password = os.getenv("DB_PASSWORD")
db_name = os.getenv("DB_NAME")
db_host = os.getenv("DB_HOST")
db_port = os.getenv("DB_PORT")

# Create an engine that knows how to connect to the database
engine = create_engine(
    f"postgresql://{db_user}:{db_password}@{db_host}:{db_port}/{db_name}"
)
# Create a Session class using the engine
Session = sessionmaker(bind=engine)

# Create a Session object
db = Session


def test_create_project():
    response = client.post("/projects", json={"id": 1000, "name": "Test Project"})
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
    response = client.post(
        "/auth",
        json={
            "name": "test",
            "email": "test@test.com",
            "password": "test",
            "role": "test",
        },
    )
    assert response.status_code == 200


def test_get_all_projects():
    # Create a new database session for the test
    db = next(get_db())

    # Delete the existing user
    db.query(User).filter(User.email == "test@test.com").delete()
    db.commit()

    # Create the User object
    test_user = User(
        name="Test User",
        email="test@test.com",
        password=generate_password_hash("test"),
        role="user",
    )

    # Add the test user to the database
    db.add(test_user)
    db.commit()

    # Authenticate
    login_response = client.post(
        "/login", data={"username": "test@test.com", "password": "test"}
    )

    # Print out the response content
    print(login_response.content)

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


def setup_test_data(db):
    with db() as session:
        session.query(User).delete()
        db.query(Project).delete()
        db.commit()

        # Create the owner
        owner = User(
            name="Owner",
            email="owner@test.com",
            password=generate_password_hash("test"),
            role="owner",
        )
        db.add(owner)

        # Create the participant
        participant = User(
            name="Participant",
            email="participant@test.com",
            password=generate_password_hash("test"),
            role="participant",
        )
        db.add(participant)

        # Create the project and assign it to the owner
        project = Project(
            id=1,
            name="Test Project",
            details=None,
            documents="{}",
            logo=None,
            owner_id=owner.id,
        )
        db.add(project)

        # Commit the changes to the database
        db.commit()


# Call the setup function before your tests
setup_test_data(db)


def test_delete_project_as_owner():
    # Authenticate as the owner
    login_response = client.post(
        "/login", data={"username": "owner@test.com", "password": "test"}
    )
    token = login_response.json()["access_token"]

    # Try to delete the project
    response = client.delete(
        "/projects/1", headers={"Authorization": f"Bearer {token}"}
    )

    # Check that the project was deleted
    assert response.status_code == 200
    assert response.json() == {"detail": "Project deleted"}


def test_delete_project_as_participant():
    # Authenticate as a participant
    login_response = client.post(
        "/login", data={"username": "participant@test.com", "password": "test"}
    )
    token = login_response.json()["access_token"]

    # Try to delete the project
    response = client.delete(
        "/projects/1", headers={"Authorization": f"Bearer {token}"}
    )

    # Check that the participant was not allowed to delete the project
    assert response.status_code == 403
