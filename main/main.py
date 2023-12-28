from fastapi import FastAPI, HTTPException
from sqlalchemy import create_engine, Column, Integer, String, Text  # noqa: F401
from sqlalchemy.orm import sessionmaker, declarative_base  # noqa: F401
from sqlalchemy.exc import OperationalError
from sqlalchemy import text
from dotenv import load_dotenv  # noqa: F401
from pydantic import BaseModel, HttpUrl
from typing import Optional, List
import os  # noqa: F401


# Load environment variables
load_dotenv()

# Get database connection details from environment variables
db_user = os.getenv("DB_USER")
db_password = os.getenv("DB_PASSWORD")
db_name = os.getenv("DB_NAME")
db_host = os.getenv("DB_HOST")
db_port = os.getenv("DB_PORT")

# Create a database engine
engine = create_engine(
    f"postgresql://{db_user}:{db_password}@{db_host}:{db_port}/{db_name}"
)

# Create a base class for declarative models
Base = declarative_base()


# Define a Project model
class Project(Base):
    __tablename__ = "projects"

    id = Column(Integer, primary_key=True)
    name = Column(String)
    logo = Column(String)
    details = Column(Text)
    documents = Column(Text)


# Create a Session class bound to this engine
Session = sessionmaker(bind=engine)


def test_db_connection():
    try:
        # Try to establish a connection and execute a query
        session = Session()
        session.execute(text("SELECT 1"))
        print("Connection to the database was successful.")
    except OperationalError:
        print("Failed to connect to the database.")
    finally:
        # Ensure the session is closed
        session.close()


test_db_connection()


# Pydantic model for project
class ProjectModel(BaseModel):
    name: str
    logo: Optional[HttpUrl] = None  # URL of the logo
    details: Optional[str] = None  # Additional details about the project
    documents: Optional[List[HttpUrl]] = []  # List of URLs of attached documents


app = FastAPI()


@app.post("/projects")
def create_project(project: ProjectModel):
    db_project = Project(**project.model_dump())
    session = Session()
    session.add(db_project)
    session.commit()
    session.refresh(db_project)
    session.close()
    return {"project_id": db_project.id, "project": project}


@app.get("/projects")
def get_all_projects():
    session = Session()
    projects = session.query(Project).all()
    session.close()
    return projects


@app.get("/project/{project_id}")
def get_project(project_id: int):
    session = Session()
    project = session.query(Project).get(project_id)
    session.close()
    if project is not None:
        return project
    else:
        raise HTTPException(status_code=404, detail="Project not found")


@app.get("/project/{project_id}/info")
def get_project_info(project_id: int):
    session = Session()
    project = session.query(Project).get(project_id)
    session.close()
    if project is not None:
        return {
            "project_id": project.id,
            "name": project.name,
            "logo": project.logo,
            "details": project.details,
            "documents": project.documents,
        }
    else:
        raise HTTPException(status_code=404, detail="Project not found")


@app.put("/project/{project_id}/info")
def update_project_info(project_id: int, project: ProjectModel):
    session = Session()
    db_project = session.query(Project).get(project_id)
    if db_project is not None:
        db_project.name = project.name
        db_project.logo = project.logo
        db_project.details = project.details
        db_project.documents = project.documents
        session.commit()
        session.refresh(db_project)
        session.close()
        return {
            "project_id": db_project.id,
            "name": db_project.name,
            "logo": db_project.logo,
            "details": db_project.details,
            "documents": db_project.documents,
        }
    else:
        session.close()
        raise HTTPException(status_code=404, detail="Project not found")


@app.delete("/project/{project_id}")
def delete_project(project_id: int):
    session = Session()
    project = session.query(Project).get(project_id)
    if project is not None:
        session.delete(project)
        session.commit()
        session.close()
        return {"message": "Project deleted"}
    else:
        raise HTTPException(status_code=404, detail="Project not found")
