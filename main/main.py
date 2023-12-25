from fastapi import FastAPI
from pydantic import BaseModel
from typing import Optional

app = FastAPI()

# In-memory storage for projects
projects = {}

# Pydantic model for project
class Project(BaseModel):
    name: str
    description: Optional[str] = None

@app.post("/projects")
def create_project(project: Project):
    project_id = str(len(projects) + 1)
    projects[project_id] = project
    return {"project_id": project_id, "project": project}

@app.get("/projects")
def get_all_projects():
    return projects

@app.get("/project/{project_id}/info")
def get_project_info(project_id: str):
    return projects.get(project_id)

@app.put("/project/{project_id}/info")
def update_project_info(project_id: str, project: Project):
    if project_id in projects:
        projects[project_id] = project
        return {"project_id": project_id, "project": project}
    else:
        return {"error": "Project not found"}

@app.delete("/project/{project_id}")
def delete_project(project_id: str):
    if project_id in projects:
        del projects[project_id]
        return {"message": "Project deleted"}
    else:
        return {"error": "Project not found"}