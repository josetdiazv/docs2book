"""
api.py — Servidor FastAPI para docs_to_book
Ejecutar: uvicorn api:app --reload --port 8000
"""

import uuid
import asyncio
import zipfile
import logging
from pathlib import Path
from datetime import datetime
from concurrent.futures import ThreadPoolExecutor
from typing import Optional

from fastapi import FastAPI, BackgroundTasks, HTTPException
from fastapi.responses import StreamingResponse, FileResponse
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, HttpUrl

from scraper import process_docs

# ── Setup ──────────────────────────────────────────────────────
logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
log = logging.getLogger("api")

app = FastAPI(
    title="📚 Docs to Book API",
    description="Convierte documentación técnica a Markdown estructurado.",
    version="1.0.0",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

OUTPUT_BASE = Path("output")
OUTPUT_BASE.mkdir(exist_ok=True)

executor = ThreadPoolExecutor(max_workers=3)

# ══════════════════════════════════════════════════════════════
#  JOBS — store en memoria (swap por Redis en producción)
# ══════════════════════════════════════════════════════════════

jobs: dict[str, dict] = {}


def make_job(job_id: str, url: str) -> dict:
    return {
        "job_id": job_id,
        "url": url,
        "status": "pending",     # pending | running | done | error
        "platform": None,
        "progress": 0,
        "total": 0,
        "current_page": "",
        "logs": [],
        "stats": None,
        "error": None,
        "created_at": datetime.utcnow().isoformat(),
        "finished_at": None,
    }


# ══════════════════════════════════════════════════════════════
#  MODELOS
# ══════════════════════════════════════════════════════════════

class ConvertRequest(BaseModel):
    url: HttpUrl
    use_js: bool = False
    export_pdf: bool = False
    max_pages: Optional[int] = None


# ══════════════════════════════════════════════════════════════
#  WORKER (se ejecuta en thread pool)
# ══════════════════════════════════════════════════════════════

def run_conversion(job_id: str, url: str, use_js: bool, export_pdf: bool):
    job = jobs[job_id]
    job["status"] = "running"
    output_dir = str(OUTPUT_BASE / job_id)

    def progress_cb(current: int, total: int, msg: str):
        job["progress"]    = current
        job["total"]       = max(total, 1)
        job["current_page"] = msg
        job["logs"].append(msg)
        log.info(f"[{job_id[:8]}] {msg}")

    try:
        stats = process_docs(
            start_url=url,
            output_dir=output_dir,
            use_js=use_js,
            export_pdf=export_pdf,
            progress_cb=progress_cb,
        )
        job["status"]      = "done"
        job["stats"]       = stats
        job["platform"]    = stats.get("platform")
        job["finished_at"] = datetime.utcnow().isoformat()

    except Exception as e:
        job["status"] = "error"
        job["error"]  = str(e)
        job["finished_at"] = datetime.utcnow().isoformat()
        log.error(f"[{job_id[:8]}] Error: {e}")


# ══════════════════════════════════════════════════════════════
#  ENDPOINTS
# ══════════════════════════════════════════════════════════════

@app.get("/", tags=["Info"])
def root():
    return {
        "service": "Docs to Book API 📚",
        "version": "1.0.0",
        "endpoints": {
            "POST /convert":              "Inicia una conversión",
            "GET  /jobs/{job_id}":        "Estado del job",
            "GET  /jobs/{job_id}/stream": "SSE — progreso en tiempo real",
            "GET  /jobs/{job_id}/download": "Descarga ZIP del libro",
            "GET  /jobs":                 "Lista todos los jobs",
        },
    }


@app.post("/convert", tags=["Conversión"], status_code=202)
def convert(req: ConvertRequest, background_tasks: BackgroundTasks):
    """
    Inicia una conversión en background.
    Retorna `job_id` para consultar el progreso.
    """
    job_id = str(uuid.uuid4())
    jobs[job_id] = make_job(job_id, str(req.url))

    background_tasks.add_task(
        run_conversion,
        job_id=job_id,
        url=str(req.url),
        use_js=req.use_js,
        export_pdf=req.export_pdf,
    )

    return {
        "job_id": job_id,
        "status": "pending",
        "stream_url": f"/jobs/{job_id}/stream",
        "status_url": f"/jobs/{job_id}",
        "download_url": f"/jobs/{job_id}/download",
    }


@app.get("/jobs", tags=["Jobs"])
def list_jobs():
    """Lista todos los jobs con su estado actual."""
    return [
        {
            "job_id":  jid,
            "url":     j["url"],
            "status":  j["status"],
            "pages":   j["stats"]["pages"] if j["stats"] else None,
            "created": j["created_at"],
        }
        for jid, j in jobs.items()
    ]


@app.get("/jobs/{job_id}", tags=["Jobs"])
def get_job(job_id: str):
    """Retorna el estado completo de un job."""
    if job_id not in jobs:
        raise HTTPException(status_code=404, detail="Job no encontrado")
    return jobs[job_id]


@app.get("/jobs/{job_id}/stream", tags=["Jobs"])
async def stream_job(job_id: str):
    """
    Server-Sent Events — retorna progreso en tiempo real.
    El cliente escucha con: `new EventSource('/jobs/<id>/stream')`
    """
    if job_id not in jobs:
        raise HTTPException(status_code=404, detail="Job no encontrado")

    async def event_generator():
        last_log_idx = 0
        while True:
            job = jobs[job_id]

            # Enviar nuevos logs
            new_logs = job["logs"][last_log_idx:]
            for msg in new_logs:
                yield f"data: {msg}\n\n"
            last_log_idx += len(new_logs)

            # Enviar progreso
            pct = int(job["progress"] / max(job["total"], 1) * 100)
            yield f"event: progress\ndata: {pct}\n\n"

            if job["status"] in ("done", "error"):
                yield f"event: {job['status']}\ndata: Job finalizado\n\n"
                break

            await asyncio.sleep(0.5)

    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )


@app.get("/jobs/{job_id}/download", tags=["Descarga"])
def download_job(job_id: str):
    """
    Descarga el resultado como ZIP (index.md + book.md + pages/ + images/).
    Solo disponible cuando status == 'done'.
    """
    if job_id not in jobs:
        raise HTTPException(status_code=404, detail="Job no encontrado")

    job = jobs[job_id]
    if job["status"] != "done":
        raise HTTPException(
            status_code=400,
            detail=f"Job no finalizado (status: {job['status']})"
        )

    job_dir = OUTPUT_BASE / job_id
    zip_path = OUTPUT_BASE / f"{job_id}.zip"

    # Crear ZIP si no existe
    if not zip_path.exists():
        with zipfile.ZipFile(zip_path, "w", zipfile.ZIP_DEFLATED) as zf:
            for file in job_dir.rglob("*"):
                if file.is_file():
                    zf.write(file, file.relative_to(job_dir))

    # Nombre limpio para el archivo
    safe_url = job["url"].replace("https://", "").replace("http://", "")
    safe_name = re.sub(r"[^\w.-]", "_", safe_url)[:40]

    return FileResponse(
        path=zip_path,
        media_type="application/zip",
        filename=f"book_{safe_name}.zip",
    )


import re  # necesario para download_job
