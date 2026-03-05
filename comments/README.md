# Comment Analysis Service (comments)

This service analyzes source code comments to produce per-file tags and a submission-level summary. It is used in this repository to evaluate student submissions placed under a submissions root.

**Submission Structure Requirements**
- Submissions are organized as directories under a submissions root. Each submission is a folder containing source files (e.g., `/student123/main.py`, `/student123/src/foo.c`).
- When you call the submission endpoint with `submission_id`, the service will analyze the directory at `$SUBMISSIONS_ROOT/<submission_id>`.

**High-level features**
- Extracts line and block comments using language token mappings.
- Produces per-file tags.
- Summarizes totals for files, lines, and comment lines at the submission level.

**Requirements**
- Python 3.14+
- Dependencies listed in `requirements.txt`.

**Running (Container)**
This repository provides `Makefile` targets that build the container, run the container, and host a variety of configuration options.

The `PRODUCTION_PORT` and `DEVELOPMENT_PORT` set the web API ports used by the service. The defaults are `80` and `8080` respectively.

Edit `HOST_SUBMISSIONS_ROOT` to point to the directory on your host containing student submissions. 

The `CONTAINER_SUBMISSIONS_ROOT` variable is the root submissions path inside the container. It is recommended leaving this unchanged, however, it will not have any functional impact if changed.

Edit `LLM_MODEL` at the top of `comments/makefile` to point to the desired OLLAMA LLM model. The model will be downloaded at runtime if not already present. By default the model is set as `granite3.1-dense:2b`.

Build and run:

```bash
make build serve
```

Build and run (development):

```bash
make dev-serve
```

Stop the production container:

```bash
make kill
```

**API**
- GET `/` — Service status. Returns `Service`, `Model`, and `Branch`

- POST `/score/submission` — Analyze a submission directory
  - Body: JSON `AnalyzeRequest`
  - Example:

```bash
curl -X POST http://localhost/score/submission \
  -H "Content-Type: application/json" \
  -d '{"submission_id":"a1/student123","ignore":["tests"]}'
```

- POST `/score/file` — Analyze a single file
  - Body: JSON `FileRequest`
  - Example (file inside a submission):

```bash
curl -X POST http://localhost/score/file \
  -H "Content-Type: application/json" \
  -d '{"submission_id":"a1/student123","file":"src/main.py"}'
```

**Output**
- The submission response contains:
  - `target`: absolute path analyzed
  - `summary`: `total_files`, `total_lines`, `total_comment_lines`
  - `files`: list of file objects. Each file object includes `path`, `lines`, `comment_lines`, `comments`, and `tags` produced by the scorer.

Example file tag values include: `all_meaningful`, `professional_language`, `good_coverage`, `todos_present`, `no_comments`, etc.

**Project Structure**
- `app/main.py` — API application and routes.
- `app/api/analyze.py` — analysis entry points for submissions and files.
- `app/api/status.py` — health/status endpoint.
- `app/utils/extractor.py` — comment extraction logic.
- `app/utils/llm.py` - LLM request handler.
- `app/utils/scoring.py` — scoring and tagging logic.
- `app/core/structs.py` — request schemas and language token mappings.
- `app/core/config.py` - scoring criteria; regex and LLM system prompt configuration.
