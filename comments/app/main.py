import os
from fastapi import FastAPI, HTTPException

from app.core.structs import AnalyzeRequest, FileRequest
from app.api.analyze import submission, file
from app.api.status import system_status

app = FastAPI(title="Comment Analysis Service", version="0.1")

@app.get("/")
def status():
    return system_status()

@app.post("/score/submission")
def analyze(req: AnalyzeRequest):
    submissions_root = os.environ.get("SUBMISSIONS_ROOT")

    if req.submission_id:
        try:
            result = submission(os.path.join(submissions_root, req.submission_id), req.ignore)
            return result
        except ValueError as ve:
            msg = str(ve)

            if msg.startswith('not_a_directory'):
                raise HTTPException(status_code=400, detail={"error": "not_a_directory", "details": msg})
            if msg.startswith('path_not_allowed'):
                raise HTTPException(status_code=400, detail={"error": "path_not_allowed", "details": msg})

            raise HTTPException(status_code=400, detail=msg)
        except Exception as e:
            raise HTTPException(status_code=500, detail=str(e))
    else:
        raise HTTPException(status_code=400, detail={"error": "missing_parameter", "message": "provide submission_id"})


@app.post("/score/file")
def analyze_single_file(req: FileRequest):
    submissions_root = os.environ.get("SUBMISSIONS_ROOT")

    if req.submission_id:
        if not submissions_root:
            raise HTTPException(status_code=500, detail="SUBMISSIONS_ROOT not configured")

        target = os.path.join(submissions_root, req.submission_id, req.file)
    else:
        target = req.file

    try:
        result = file(target)
        return result
    except ValueError as ve:
        msg = str(ve)

        if msg.startswith('not_a_directory'):
            raise HTTPException(status_code=400, detail={"error": "not_a_directory", "details": msg})
        if msg.startswith('path_not_allowed'):
            raise HTTPException(status_code=400, detail={"error": "path_not_allowed", "details": msg})

        raise HTTPException(status_code=400, detail=msg)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
