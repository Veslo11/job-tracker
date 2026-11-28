from contextlib import asynccontextmanager
from datetime import date
from typing import Optional

from fastapi import Depends, FastAPI, HTTPException
from sqlmodel import Field, Session, SQLModel, create_engine, select
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from enum import Enum

DATABASE_URL = "sqlite:///jobs.db"
engine = create_engine(DATABASE_URL, connect_args={"check_same_thread": False})

class Status(str, Enum):
    applied="applied"
    interview="interview"
    offer="offer"
    rejected="rejected"

class JobBase(SQLModel):
    company: str
    position: str
    status: Status = Status.applied  # applied, interview, offer, rejected
    date_applied: date = Field(default_factory=date.today)
    notes: Optional[str] = None


class Job(JobBase, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)


class JobCreate(JobBase):
    pass


class JobUpdate(SQLModel):
    company: Optional[str] = None
    position: Optional[str] = None
    status: Optional[Status] = None
    date_applied: Optional[date] = None
    notes: Optional[str] = None


def get_session():
    with Session(engine) as session:
        yield session


@asynccontextmanager
async def lifespan(app: FastAPI):
    SQLModel.metadata.create_all(engine)
    yield


app = FastAPI(title="Job Tracker", lifespan=lifespan)

app.mount("/static", StaticFiles(directory="static"), name="static")


@app.get("/", include_in_schema=False)
def index():
    return FileResponse("static/index.html")

@app.get("/health")
def health():
    return {"status": "ok"}


@app.post("/jobs", response_model=Job, status_code=201)
def create_job(job: JobCreate, session: Session = Depends(get_session)):
    db_job = Job.model_validate(job)
    session.add(db_job)
    session.commit()
    session.refresh(db_job)
    return db_job


@app.get("/jobs", response_model=list[Job])
def list_jobs(status: Optional[Status] = None, session: Session = Depends(get_session)):

    if status is not None:
        return session.exec(select(Job).where(Job.status == status)).all()
    else  :
        return session.exec(select(Job)).all()


@app.get("/jobs/{job_id}", response_model=Job)
def get_job(job_id: int, session: Session = Depends(get_session)):
    job = session.get(Job, job_id)
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")
    return job


@app.patch("/jobs/{job_id}", response_model=Job)
def update_job(job_id: int, changes: JobUpdate, session: Session = Depends(get_session)):
    job = session.get(Job, job_id)
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")
    job.sqlmodel_update(changes.model_dump(exclude_unset=True))
    session.add(job)
    session.commit()
    session.refresh(job)
    return job


@app.delete("/jobs/{job_id}", status_code=204)
def delete_job(job_id: int, session: Session = Depends(get_session)):
    job = session.get(Job, job_id)
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")
    session.delete(job)
    session.commit()