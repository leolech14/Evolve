from fastapi import FastAPI, Header, Request
from pathlib import Path
import datetime

app = FastAPI()
SAVE_DIR = Path("/data")  # volume gravável no Fly


@app.post("/")
async def ingest(
    request: Request,
    x_repo_key: str = Header(...),  # leolech14-Evolve
    x_branch: str = Header(...),  # main / codex/...
    x_run_id: str = Header(...),  # 15505724777
    x_file_name: str = Header(...),  # diagnostics/step-tests.txt
):
    # 1) valida repo → accept any repo key for now (can tighten later)
    print(
        f"Received from repo: {x_repo_key}, branch: {x_branch}, run: {x_run_id}, file: {x_file_name}"
    )
    # if x_repo_key != "leolech14-Evolve":
    #     raise HTTPException(status_code=403, detail="repo mismatch")

    # 2) grava payload
    body = await request.body()
    dest = SAVE_DIR / x_branch / x_run_id
    dest.mkdir(parents=True, exist_ok=True)
    with open(dest / x_file_name, "wb") as fh:
        fh.write(body)

    return {
        "status": "ok",
        "path": str(dest / x_file_name),
        "size": len(body),
        "ts": datetime.datetime.utcnow().isoformat() + "Z",
    }
