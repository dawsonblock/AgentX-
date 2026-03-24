"""Run API routes."""

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from pydantic import BaseModel

from api.deps import get_db
from services.run_service import RunService
from services.patch_service import PatchService
from services.approval_service import ApprovalService
from services.artifact_service import ArtifactService
from services.provenance_service import ProvenanceService
from services.ci_service import CIService
from runtime.executor import RunExecutor, ServiceBundle
from runtime.event_store import EventStore
from orchestrator import worktree, context_builder
from worker.llm_worker import LLMWorker

router = APIRouter()


class CreateRunRequest(BaseModel):
    """Create run request."""
    task: str
    repo: str


class CreateRunResponse(BaseModel):
    """Create run response."""
    run_id: str
    patch_id: str
    status: str


def _create_service_bundle(db: Session) -> ServiceBundle:
    """Create service bundle for executor."""
    return ServiceBundle(
        db=db,
        run=RunService(db),
        patch=PatchService(db),
        approval=ApprovalService(db),
        artifact=ArtifactService(db),
        prov=ProvenanceService(db),
        events=EventStore(db),
        ci=CIService(),
        orch=type("Orch", (), {
            "allocate": worktree.allocate,
            "build_context": context_builder.build_context
        })(),
        worker=LLMWorker()
    )


@router.post("/", response_model=CreateRunResponse)
def create_run(request: CreateRunRequest, db: Session = Depends(get_db)):
    """Create and execute a new run.
    
    Args:
        request: Run creation request
        db: Database session
        
    Returns:
        Created run and patch info
    """
    # Create run
    run_svc = RunService(db)
    run = run_svc.create(task=request.task, repo=request.repo)
    
    # Execute run
    services = _create_service_bundle(db)
    executor = RunExecutor(db, services)
    
    try:
        patch = executor.execute(run.id)
        return CreateRunResponse(
            run_id=run.id,
            patch_id=patch.id,
            status=run.state
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/{run_id}")
def get_run(run_id: str, db: Session = Depends(get_db)):
    """Get run details."""
    run = RunService(db).get(run_id)
    if not run:
        raise HTTPException(status_code=404, detail="Run not found")
    return {
        "id": run.id,
        "task": run.task,
        "repo": run.repo,
        "state": run.state,
        "created_at": run.created_at,
        "patches": [{"id": p.id, "status": p.status} for p in run.patches]
    }


@router.get("/")
def list_runs(limit: int = 100, db: Session = Depends(get_db)):
    """List all runs."""
    runs = RunService(db).list_all(limit=limit)
    return [
        {
            "id": r.id,
            "task": r.task[:50] + "..." if len(r.task) > 50 else r.task,
            "repo": r.repo,
            "state": r.state,
            "created_at": r.created_at
        }
        for r in runs
    ]
