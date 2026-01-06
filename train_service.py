# train_service.py
# Minimal HTTP API to start and monitor Kuiper training jobs.

import subprocess
import uuid
from pathlib import Path
from typing import Dict, Optional

from fastapi import FastAPI, HTTPException
from pydantic import BaseModel

from kuiper_common import PROJECT_ROOT

app = FastAPI(title="Kuiper Training Service")


class TrainRequest(BaseModel):
    data_root: Optional[Path] = None
    voice_name: Optional[str] = None
    batch_size: Optional[int] = None
    accelerator: Optional[str] = None
    devices: Optional[str] = None
    force_cpu: bool = False


class TrainStatus(BaseModel):
    job_id: str
    status: str
    return_code: Optional[int] = None
    log_path: Optional[Path] = None


_jobs: Dict[str, Dict] = {}


@app.post("/train", response_model=TrainStatus)
def start_train(req: TrainRequest):
    job_id = str(uuid.uuid4())
    log_path = PROJECT_ROOT / "logs" / f"train_{job_id}.log"
    log_path.parent.mkdir(parents=True, exist_ok=True)

    cmd = ["python", "-u", str(PROJECT_ROOT / "kuiper-train.py")]
    if req.data_root:
        cmd += ["--data-root", str(req.data_root)]
    if req.voice_name:
        cmd += ["--voice-name", req.voice_name]
    if req.batch_size is not None:
        cmd += ["--batch-size", str(req.batch_size)]
    if req.accelerator:
        cmd += ["--accelerator", req.accelerator]
    if req.devices:
        cmd += ["--devices", req.devices]
    if req.force_cpu:
        cmd.append("--force-cpu")

    fp = log_path.open("w", buffering=1, encoding="utf-8")
    proc = subprocess.Popen(cmd, stdout=fp, stderr=subprocess.STDOUT)

    _jobs[job_id] = {"proc": proc, "log_path": log_path, "fp": fp}

    return TrainStatus(job_id=job_id, status="running", log_path=log_path)


@app.get("/train/{job_id}", response_model=TrainStatus)
def get_status(job_id: str):
    job = _jobs.get(job_id)
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")

    proc = job["proc"]
    code = proc.poll()
    if code is None:
        status = "running"
    else:
        status = "succeeded" if code == 0 else "failed"
        if not job.get("closed"):
            job["fp"].close()
            job["closed"] = True

    return TrainStatus(job_id=job_id, status=status, return_code=code, log_path=job["log_path"])

