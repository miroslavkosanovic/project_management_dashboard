from fastapi import FastAPI, HTTPException, Depends, status, UploadFile, File
from fastapi.security import OAuth2PasswordBearer, OAuth2PasswordRequestForm
from sqlalchemy import (
    create_engine,
    Boolean,
    Table,
    MetaData,
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
from sqlalchemy.orm import joinedload
import boto3

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

oauth2_scheme = OAuth2PasswordBearer(tokenUrl="token")


class UserCreate(BaseModel):
    name: str
    email: str
    password: str
    role: Optional[str] = "user"


class ProjectUser(Base):
    __tablename__ = "project_users"
    __table_args__ = {"extend_existing": True}

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"))
    project_id = Column(Integer, ForeignKey("projects.id"))
    is_owner = Column(
        Boolean, default=False
    )  # This line is for the ownership information
    user = relationship("User", back_populates="project_users")
    project = relationship("Project", back_populates="project_users")


class User(Base):
    __tablename__ = "users"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String)
    email = Column(String, unique=True)
    password = Column(String)
    role = Column(String)
    active = Column(Boolean, default=True)
    project_users = relationship("ProjectUser", back_populates="user")


class Project(Base):
    __tablename__ = "projects"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String)
    logo = Column(String)
    details = Column(Text)
    documents = Column(Text)
    project_users = relationship("ProjectUser", back_populates="project")
    documents = relationship("Document", back_populates="project")


# Define the documents table
metadata = MetaData()
documents = Table(
    "documents",
    metadata,
    Column("id", Integer, primary_key=True),
    Column("project_id", Integer, ForeignKey("projects.id")),
    Column("url", String),
)


# Add a Document model
class Document(Base):
    __tablename__ = "documents"

    id = Column(Integer, primary_key=True, index=True)
    project_id = Column(Integer, ForeignKey("projects.id"))
    url = Column(String)
    project = relationship("Project", back_populates="documents")
    def to_dict(self):
        return {c.key: getattr(self, c.key) for c in inspect(self).mapper.column_attrs}


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
    db = SessionLocal()
    db_project = Project(**project.dict())
    db.add(db_project)
    db.commit()
    db.refresh(db_project)
    db.close()
    return {"project_id": db_project.id, "project": project}


@app.get("/project/{project_id}/info")
def get_project_info(project_id: int):
    db = SessionLocal()
    project = db.query(Project).options(joinedload(Project.documents)).get(project_id)
    if project is not None:
        response = {
            "project_id": project.id,
            "name": project.name,
            "logo": project.logo,
            "details": project.details,
            "documents": [
                doc.to_dict() for doc in project.documents
            ],  # assuming Document has a to_dict method
        }
    else:
        response = HTTPException(status_code=404, detail="Project not found")
    db.close()
    return response


def get_project_with_documents(project_id):
    db = SessionLocal()
    try:
        project = (
            db.query(Project).options(joinedload(Project.documents)).get(project_id)
        )
        return project
    finally:
        db.close()


@app.put("/project/{project_id}/info")
def update_project_info(project_id: int, project_info: ProjectModel):
    db = SessionLocal()
    db_project = db.query(Project).get(project_id)
    if db_project is not None:
        db_project.name = project_info.name
        db_project.logo = project_info.logo
        db_project.details = project_info.details

        # Clear the existing documents and add the new ones
        db_project.documents = []
        for doc in project_info.documents:
            db_project.documents.append(doc)

        db.commit()
        db.refresh(db_project)

        # Access the documents attribute before closing the session
        documents = [doc.to_dict() for doc in db_project.documents]

        db.close()
        return {
            "project_id": db_project.id,
            "name": db_project.name,
            "logo": db_project.logo,
            "details": db_project.details,
            "documents": documents,
        }
    else:
        db.close()
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
    if not any(
        current_user.id == project_user.user_id
        for project_user in project.project_users
    ):
        raise HTTPException(status_code=403, detail="Not authorized")
    db.delete(project)
    db.commit()
    return {"message": "Project deleted successfully"}


@app.post("/project/{project_id}/invite")
def invite_user(
    project_id: int,
    user_email: str = Query(...),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
):
    # Check if the current user is the owner of the project
    project_user = (
        db.query(ProjectUser)
        .filter(
            ProjectUser.project_id == project_id,
            ProjectUser.user_id == current_user.id,
            ProjectUser.is_owner,
        )
        .first()
    )

    if project_user is None:
        raise HTTPException(status_code=403, detail="Not authorized")

    # Check if the user to be invited exists
    user = db.query(User).filter(User.email == user_email).first()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")

    # Check if the user is already a member of the project
    is_already_member = (
        db.query(ProjectUser)
        .filter(ProjectUser.project_id == project_id, ProjectUser.user_id == user.id)
        .first()
    )

    if is_already_member is not None:
        raise HTTPException(
            status_code=400, detail="User is already a member of the project"
        )

    # Add the user to the project
    new_project_user = ProjectUser(
        user_id=user.id, project_id=project_id, is_owner=False
    )
    db.add(new_project_user)
    db.commit()

    return {"message": "User invited successfully"}


s3 = boto3.client("s3")


async def upload_file_to_s3(file: UploadFile):
    try:
        s3.upload_fileobj(file.file, "your-bucket-name", file.filename)
        return f"https://myapp-prod-documents.s3.amazonaws.com/{file.filename}"
    except Exception as e:
        print(e)
        return False


# Add an endpoint to upload a document
@app.post("/projects/{project_id}/documents")
async def upload_document(project_id: int, file: UploadFile = File(...)):
    # Upload the file to a storage service and get the URL
    url = await upload_file_to_s3(file)

    # Save a new document in the database
    db = SessionLocal()
    document = Document(url=url, project_id=project_id)
    db.add(document)
    db.commit()

    return {"url": url}


# Modify the project endpoints to include the documents
@app.get("/projects", dependencies=[Depends(get_current_user)])
def get_all_projects():
    db = SessionLocal()
    projects = db.query(Project).options(joinedload(Project.documents)).all()
    db.close()
    return projects


@app.get("/project/{project_id}/documents")
def get_project_documents(project_id: int):
    db = SessionLocal()
    db_project = db.query(Project).get(project_id)
    if db_project is None:
        db.close()
        raise HTTPException(status_code=404, detail="Project not found")

    # Get the documents of the project
    documents = [doc.to_dict() for doc in db_project.documents]

    db.close()
    return {"documents": documents}


@app.get("/project/{project_id}", dependencies=[Depends(get_current_user)])
def get_project(project_id: int):
    db = SessionLocal()
    project = db.query(Project).options(joinedload(Project.documents)).get(project_id)
    if project is not None:
        response = project
    else:
        response = HTTPException(status_code=404, detail="Project not found")
    db.close()
    return response
