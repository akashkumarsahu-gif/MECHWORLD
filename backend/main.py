import os
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Optional

from dotenv import load_dotenv
from fastapi import FastAPI, Depends, HTTPException, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.security import OAuth2PasswordBearer
from fastapi.staticfiles import StaticFiles
from jose import JWTError, jwt
from pwdlib import PasswordHash
from pydantic import BaseModel, EmailStr, Field
from sqlalchemy import Boolean, DateTime, ForeignKey, Integer, String, Text, create_engine, select
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship, sessionmaker, Session

BASE_DIR = Path(__file__).resolve().parent.parent
load_dotenv(BASE_DIR / ".env")
SECRET_KEY = os.getenv("SECRET_KEY", "local-development-only-change-me")
ALGORITHM = "HS256"
TOKEN_MINUTES = 60 * 24
ADMIN_EMAIL = os.getenv("ADMIN_EMAIL", "").strip().lower()
DATABASE_URL = os.getenv("DATABASE_URL", "").strip() or f"sqlite:///{BASE_DIR / 'mechworld.db'}"

engine_args = {"check_same_thread": False} if DATABASE_URL.startswith("sqlite") else {}
engine = create_engine(DATABASE_URL, connect_args=engine_args, pool_pre_ping=True)
SessionLocal = sessionmaker(bind=engine, autoflush=False, autocommit=False)

class Base(DeclarativeBase):
    pass

class User(Base):
    __tablename__ = "users"
    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    name: Mapped[str] = mapped_column(String(80))
    email: Mapped[str] = mapped_column(String(255), unique=True, index=True)
    password_hash: Mapped[str] = mapped_column(String(255))
    is_admin: Mapped[bool] = mapped_column(Boolean, default=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))
    projects: Mapped[list["SavedProject"]] = relationship(back_populates="owner", cascade="all, delete-orphan")
    calculations: Mapped[list["Calculation"]] = relationship(back_populates="owner", cascade="all, delete-orphan")

class SavedProject(Base):
    __tablename__ = "saved_projects"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    title: Mapped[str] = mapped_column(String(120))
    description: Mapped[str] = mapped_column(Text, default="")
    technology: Mapped[str] = mapped_column(String(200), default="")
    link: Mapped[str] = mapped_column(String(500), default="")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"))
    owner: Mapped[User] = relationship(back_populates="projects")

class Calculation(Base):
    __tablename__ = "calculations"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    tool: Mapped[str] = mapped_column(String(80))
    inputs_json: Mapped[str] = mapped_column(Text)
    result: Mapped[str] = mapped_column(String(250))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"))
    owner: Mapped[User] = relationship(back_populates="calculations")

class ContactMessage(Base):
    __tablename__ = "contact_messages"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    name: Mapped[str] = mapped_column(String(80))
    email: Mapped[str] = mapped_column(String(255))
    subject: Mapped[str] = mapped_column(String(160))
    message: Mapped[str] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))

Base.metadata.create_all(bind=engine)
app = FastAPI(title="MECHWORLD API", version="1.0.0", description="Authentication, projects, engineering calculation history, and contact API.")
app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_credentials=False, allow_methods=["*"], allow_headers=["*"])
password_hash = PasswordHash.recommended()
oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/api/auth/login", auto_error=False)

def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

class RegisterIn(BaseModel):
    name: str = Field(min_length=2, max_length=80)
    email: EmailStr
    password: str = Field(min_length=8, max_length=128)

class LoginIn(BaseModel):
    email: EmailStr
    password: str = Field(min_length=8, max_length=128)

class ProjectIn(BaseModel):
    title: str = Field(min_length=2, max_length=120)
    description: str = Field(default="", max_length=4000)
    technology: str = Field(default="", max_length=200)
    link: str = Field(default="", max_length=500)

class CalculationIn(BaseModel):
    tool: str = Field(min_length=1, max_length=80)
    inputs: dict
    result: str = Field(min_length=1, max_length=250)

class ContactIn(BaseModel):
    name: str = Field(min_length=2, max_length=80)
    email: EmailStr
    subject: str = Field(min_length=2, max_length=160)
    message: str = Field(min_length=5, max_length=5000)

def user_view(user: User):
    return {"id": user.id, "name": user.name, "email": user.email, "is_admin": user.is_admin, "created_at": user.created_at.isoformat()}

def make_token(user: User):
    now = datetime.now(timezone.utc)
    return jwt.encode({"sub": str(user.id), "email": user.email, "iat": now, "exp": now + timedelta(minutes=TOKEN_MINUTES)}, SECRET_KEY, algorithm=ALGORITHM)

def current_user(token: Optional[str] = Depends(oauth2_scheme), db: Session = Depends(get_db)):
    if not token:
        raise HTTPException(status_code=401, detail="Please log in first.")
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        user_id = int(payload.get("sub", "0"))
    except (JWTError, ValueError):
        raise HTTPException(status_code=401, detail="Session expired or invalid. Please log in again.")
    user = db.get(User, user_id)
    if not user:
        raise HTTPException(status_code=401, detail="Account not found.")
    return user

def admin_user(user: User = Depends(current_user)):
    if not user.is_admin:
        raise HTTPException(status_code=403, detail="Admin access required.")
    return user

@app.get("/api/health")
def health():
    return {"status": "ok", "service": "MECHWORLD API"}

@app.post("/api/auth/register", status_code=201)
def register(data: RegisterIn, db: Session = Depends(get_db)):
    email = str(data.email).lower()
    if db.scalar(select(User).where(User.email == email)):
        raise HTTPException(status_code=409, detail="An account with this email already exists.")
    user = User(name=data.name.strip(), email=email, password_hash=password_hash.hash(data.password), is_admin=bool(ADMIN_EMAIL and email == ADMIN_EMAIL))
    db.add(user); db.commit(); db.refresh(user)
    return {"access_token": make_token(user), "token_type": "bearer", "user": user_view(user)}

@app.post("/api/auth/login")
def login(data: LoginIn, db: Session = Depends(get_db)):
    email = str(data.email).lower()
    user = db.scalar(select(User).where(User.email == email))
    if not user or not password_hash.verify(data.password, user.password_hash):
        raise HTTPException(status_code=401, detail="Email or password is incorrect.")
    return {"access_token": make_token(user), "token_type": "bearer", "user": user_view(user)}

@app.get("/api/auth/me")
def me(user: User = Depends(current_user)):
    return user_view(user)

@app.post("/api/projects", status_code=201)
def create_project(data: ProjectIn, user: User = Depends(current_user), db: Session = Depends(get_db)):
    item = SavedProject(**data.model_dump(), user_id=user.id)
    db.add(item); db.commit(); db.refresh(item)
    return project_view(item)

def project_view(item: SavedProject):
    return {"id": item.id, "title": item.title, "description": item.description, "technology": item.technology, "link": item.link, "created_at": item.created_at.isoformat()}

@app.get("/api/projects")
def list_projects(user: User = Depends(current_user), db: Session = Depends(get_db)):
    return [project_view(x) for x in db.scalars(select(SavedProject).where(SavedProject.user_id == user.id).order_by(SavedProject.id.desc())).all()]

@app.delete("/api/projects/{project_id}")
def delete_project(project_id: int, user: User = Depends(current_user), db: Session = Depends(get_db)):
    item = db.get(SavedProject, project_id)
    if not item or item.user_id != user.id:
        raise HTTPException(status_code=404, detail="Project not found.")
    db.delete(item); db.commit()
    return {"message": "Project deleted."}

@app.post("/api/calculations", status_code=201)
def save_calculation(data: CalculationIn, user: User = Depends(current_user), db: Session = Depends(get_db)):
    import json
    item = Calculation(tool=data.tool, inputs_json=json.dumps(data.inputs), result=data.result, user_id=user.id)
    db.add(item); db.commit(); db.refresh(item)
    return {"id": item.id, "tool": item.tool, "inputs": data.inputs, "result": item.result, "created_at": item.created_at.isoformat()}

@app.get("/api/calculations")
def list_calculations(user: User = Depends(current_user), db: Session = Depends(get_db)):
    import json
    rows = db.scalars(select(Calculation).where(Calculation.user_id == user.id).order_by(Calculation.id.desc()).limit(100)).all()
    return [{"id": x.id, "tool": x.tool, "inputs": json.loads(x.inputs_json), "result": x.result, "created_at": x.created_at.isoformat()} for x in rows]

@app.post("/api/contact", status_code=201)
def contact(data: ContactIn, db: Session = Depends(get_db)):
    item = ContactMessage(name=data.name.strip(), email=str(data.email).lower(), subject=data.subject.strip(), message=data.message.strip())
    db.add(item); db.commit(); db.refresh(item)
    return {"message": "Thanks! Your message has been saved."}

@app.get("/api/admin/messages")
def admin_messages(user: User = Depends(admin_user), db: Session = Depends(get_db)):
    rows = db.scalars(select(ContactMessage).order_by(ContactMessage.id.desc()).limit(200)).all()
    return [{"id": x.id, "name": x.name, "email": x.email, "subject": x.subject, "message": x.message, "created_at": x.created_at.isoformat()} for x in rows]

@app.get("/api/admin/users")
def admin_users(user: User = Depends(admin_user), db: Session = Depends(get_db)):
    return [user_view(x) for x in db.scalars(select(User).order_by(User.id.desc()).limit(500)).all()]

# Serve the existing static website from the same origin as the API.
app.mount("/", StaticFiles(directory=str(BASE_DIR), html=True, check_dir=True), name="site")
