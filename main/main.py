from fastapi import FastAPI, HTTPException, Depends, status
from fastapi.security import OAuth2PasswordBearer, OAuth2PasswordRequestForm
from sqlalchemy import (
    create_engine,
    Table,
    Boolean,
    ForeignKey,
    Column,
    Integer,
    String,
    Text,
)  # noqa: F401
from sqlalchemy.orm import sessionmaker, relationship, declarative_base  # noqa: F401
from dotenv import load_dotenv  # noqa: F401
from pydantic import BaseModel, HttpUrl
from typing import Optional, List
import os  # noqa: F401
from werkzeug.security import generate_password_hash, check_password_hash
import jwt
from jwt import PyJWTError, InvalidTokenError
from datetime import datetime, timedelta
from fastapi import Query

# Load environment variables
load_dotenv()

# Get database connection details from environment variables
db_user = os.getenv("DB_USER")
db_password = os.getenv("DB_PASSWORD")
db_name = os.getenv("DB_NAME")
db_host = os.getenv("DB_HOST")
db_port = os.getenv("DB_PORT")
SECRET_KEY = os.getenv("JWT_SECRET")
ALGORITHM = "HS256"

# Create a database engine
engine = create_engine(
    f"postgresql://{db_user}:{db_password}@{db_host}:{db_port}/{db_name}"
)


def create_access_token(data: dict, expires_delta: timedelta = None):
    to_encode = data.copy()
    if expires_delta:
        expire = datetime.utcnow() + expires_delta
    else:
        expire = datetime.utcnow() + timedelta(minutes=15)
    to_encode.update({"exp": expire})
    encoded_jwt = jwt.encode(to_encode, SECRET_KEY, algorithm=ALGORITHM)
    return encoded_jwt


# Create a base class for declarative models
Base = declarative_base()


class UserLogin(BaseModel):
    email: str
    password: str


oauth2_scheme = OAuth2PasswordBearer(tokenUrl="token")


class UserCreate(BaseModel):
    name: str
    email: str
    password: str
    role: Optional[str] = "user"


# Association table
project_users = Table(
    "project_users",
    Base.metadata,
    Column("user_id", Integer, ForeignKey("users.id")),
    Column("project_id", Integer, ForeignKey("projects.id")),
)


class User(Base):
    __tablename__ = "users"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String)
    email = Column(String, unique=True)
    password = Column(String)
    role = Column(String)
    active = Column(Boolean, default=True)
    projects = relationship("Project", secondary=project_users, back_populates="users")


# Define a Project model
class Project(Base):
    __tablename__ = "projects"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String)
    logo = Column(String)
    details = Column(Text)
    documents = Column(Text)
    users = relationship("User", secondary=project_users, back_populates="projects")


# Create all tables in the engine
Base.metadata.create_all(engine)

# Create a Session class bound to this engine
Session = sessionmaker(bind=engine)

SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/login")


# Pydantic model for project
class ProjectModel(BaseModel):
    name: str
    logo: Optional[HttpUrl] = None  # URL of the logo
    details: Optional[str] = None  # Additional details about the project
    documents: Optional[List[HttpUrl]] = []  # List of URLs of attached documents


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


app = FastAPI()


@app.post("/auth", response_model=UserCreate)
def create_user(user: UserCreate, db: Session = Depends(get_db)):
    hashed_password = generate_password_hash(user.password)

    db_user = User(
        name=user.name, email=user.email, password=hashed_password, role=user.role
    )

    db.add(db_user)
    db.commit()

    return db_user


@app.post("/login")
def login(
    form_data: OAuth2PasswordRequestForm = Depends(), db: Session = Depends(get_db)
):
    user = db.query(User).filter(User.email == form_data.username).first()

    if not user or not check_password_hash(user.password, form_data.password):
        raise HTTPException(status_code=400, detail="Incorrect username or password")

    access_token_expires = timedelta(minutes=30)
    access_token = create_access_token(
        data={"sub": user.email}, expires_delta=access_token_expires
    )
    return {"access_token": access_token, "token_type": "bearer"}


credentials_exception = HTTPException(
    status_code=status.HTTP_401_UNAUTHORIZED,
    detail="Could not validate credentials",
    headers={"WWW-Authenticate": "Bearer"},
)


class TokenData(BaseModel):
    email: str


def decode_access_token(token: str):
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        email: str = payload.get("sub")
        if email is None:
            raise credentials_exception
        return payload
    except (PyJWTError, InvalidTokenError):
        raise credentials_exception


def get_current_user(
    db: Session = Depends(get_db), token: str = Depends(oauth2_scheme)
):
    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Could not validate credentials",
        headers={"WWW-Authenticate": "Bearer"},
    )
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        email: str = payload.get("sub")
        if email is None:
            raise credentials_exception
        token_data = TokenData(email=email)
    except Exception:
        raise credentials_exception
    user = db.query(User).filter(User.email == token_data.email).first()
    if user is None:
        raise credentials_exception
    if not user.active:
        raise HTTPException(status_code=400, detail="Inactive user")
    return user


@app.post("/projects")
def create_project(project: ProjectModel):
    db_project = Project(**project.model_dump())
    session = Session()
    session.add(db_project)
    session.commit()
    session.refresh(db_project)
    session.close()
    return {"project_id": db_project.id, "project": project}


@app.get("/projects", dependencies=[Depends(get_current_user)])
def get_all_projects():
    session = Session()
    projects = session.query(Project).all()
    session.close()
    return projects


@app.get("/project/{project_id}", dependencies=[Depends(get_current_user)])
def get_project(project_id: int):
    session = Session()
    project = session.get(Project, project_id)
    session.close()
    if project is not None:
        return project
    else:
        raise HTTPException(status_code=404, detail="Project not found")


@app.get("/project/{project_id}/info")
def get_project_info(project_id: int):
    session = Session()
    project = session.get(Project, project_id)
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
    db_project = session.get(Project, project_id)
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


def get_current_active_user(current_user: User = Depends(get_current_user)):
    if not current_user.active:
        raise HTTPException(status_code=400, detail="Inactive user")
    return current_user


@app.delete("/projects/{project_id}")
def delete_project(
    project_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
):
    project = db.query(Project).filter(Project.id == project_id).first()
    if not project:
        raise HTTPException(status_code=404, detail="Project not found")
    if current_user not in project.users:
        raise HTTPException(status_code=403, detail="Not authorized")
    db.delete(project)
    db.commit()
    return {"message": "Project deleted successfully"}

@app.post("/project/{project_id}/invite")
def invite_user(
    project_id: int,
    user_login: str = Query(...),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
):
    project = db.query(Project).filter(Project.id == project_id).first()
    if not project:
        raise HTTPException(status_code=404, detail="Project not found")

    if project.owner != current_user:
        raise HTTPException(status_code=403, detail="Not authorized")

    user = db.query(User).filter(User.login == user_login).first()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")

    project.users.append(user)
    db.commit()

    return {"message": "User invited successfully"}