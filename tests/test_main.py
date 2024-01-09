from fastapi.testclient import TestClient
from main.main import app, get_db, User, Project, ProjectUser, Document
from werkzeug.security import generate_password_hash
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
import os

client = TestClient(app)

db_user = os.getenv("DB_USER")
db_password = os.getenv("DB_PASSWORD")
db_name = os.getenv("DB_NAME")
db_host = os.getenv("DB_HOST")
db_port = os.getenv("DB_PORT")

# Create a database engine
engine = create_engine(
    f"postgresql://{db_user}:{db_password}@{db_host}:{db_port}/{db_name}"
)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

app.dependency_overrides[get_db] = get_db

client = TestClient(app)


def setup_test_data(db):
    # Delete existing data
    db.query(ProjectUser).delete()
    db.query(User).delete()
    db.query(Project).delete()

    # Create test users
    test_user = User(
        name="Test User",
        email="test@test.com",
        password=generate_password_hash("test"),
        role="user",
    )

    test_user2 = User(
        name="Test User User",
        email="user@test.com",
        password=generate_password_hash("test"),
        role="user",
    )

    test_user3 = User(
        name="Test User Owner",
        email="owner@test.com",
        password=generate_password_hash("test"),
        role="user",
    )

    db.add_all([test_user, test_user2, test_user3])
    db.commit()

    # Create test project and associate it with test_user3
    test_project = Project(
        name="Test Project",
    )

    # Create a ProjectUser object
    project_user = ProjectUser(user=test_user3, project=test_project, is_owner=True)

    # Add the ProjectUser object to the session
    db.add(project_user)
    db.commit()


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
            "documents": [],
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
        "documents": [],
        "logo": None,
    }


def test_update_project_info():
    response = client.put("/project/1/info", json={"name": "Updated Project"})
    assert response.status_code == 200
    assert response.json() == {
        "project_id": 1,
        "name": "Updated Project",
        "details": None,
        "documents": [],
        "logo": None,
    }


def test_delete_project():
    # Create a new database session for the test
    db = SessionLocal()

    # Set up test data
    setup_test_data(db)

    # Authenticate as the project owner
    login_response = client.post(
        "/login", data={"username": "owner@test.com", "password": "test"}
    )
    assert login_response.status_code == 200
    token = login_response.json()["access_token"]

    # Get the id of the test project
    test_project_id = (
        db.query(Project).filter(Project.name == "Test Project").first().id
    )

    # Send the DELETE request with the authentication token
    response = client.delete(
        f"/projects/{test_project_id}", headers={"Authorization": f"Bearer {token}"}
    )

    assert response.status_code == 200
    assert response.json() == {"message": "Project deleted successfully"}


def test_invite_user():
    # Create a new database session for the test
    db = SessionLocal()

    # Set up test data
    setup_test_data(db)

    # Authenticate as the project owner
    login_response = client.post(
        "/login", data={"username": "owner@test.com", "password": "test"}
    )
    assert login_response.status_code == 200
    token = login_response.json()["access_token"]

    # Get the id of the test project and the email of the user to be invited
    test_project_id = (
        db.query(Project).filter(Project.name == "Test Project").first().id
    )
    user_to_invite_email = (
        db.query(User).filter(User.email == "user@test.com").first().email
    )

    # Send the POST request with the authentication token
    response = client.post(
        f"/project/{test_project_id}/invite?user_email={user_to_invite_email}",
        headers={"Authorization": f"Bearer {token}"},
    )

    # Check the response
    assert response.status_code == 200
    assert response.json() == {"message": "User invited successfully"}

    # Check that the user was actually invited
    updated_project = db.query(Project).filter(Project.id == test_project_id).first()
    assert user_to_invite_email in [
        pu.user.email for pu in updated_project.project_users
    ]


def test_get_project_documents():
    # Create a test project and document
    db = SessionLocal()
    test_project = Project(
        name="Test Project", logo="Test Logo", details="Test Details"
    )
    db.add(test_project)
    db.commit()
    db.refresh(test_project)

    test_document = Document(url="Test Document URL", project_id=test_project.id)
    db.add(test_document)
    db.commit()
    db.refresh(test_document)

    db.close()

    # Make a request to the endpoint
    response = client.get(f"/project/{test_project.id}/documents")

    # Check that the response is successful
    assert response.status_code == 200

    # Check that the returned documents match the test document
    assert response.json() == {"documents": [test_document.url]}
