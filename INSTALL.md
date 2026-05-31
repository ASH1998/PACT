# INSTALL

## Backend setup with `uv`

These steps create the virtual environment at the repository root as `./.venv`
and install the backend dependencies from `backend/pyproject.toml`.

```bash
cd /path/to/PACT
uv venv .venv
source .venv/bin/activate
uv sync --project backend --active --extra dev --link-mode=copy
cp backend/.env.example backend/.env
```

Notes:

- The active virtual environment lives at `PACT/.venv`.
- `--project backend` tells `uv` to read the backend project metadata from
  `backend/pyproject.toml`.
- `--active` installs into the currently activated root virtual environment.
  If your shell is still in another env such as Conda `base`, `uv` can create
  `backend/.venv` instead.
- `--extra dev` includes the backend test and lint dependencies.

## Run the backend

```bash
cd /path/to/PACT
source .venv/bin/activate
uv run --project backend --active uvicorn app.main:app --app-dir backend --reload --port 8000
```

If you do not want to rely on shell activation, use:

```bash
cd /path/to/PACT
.venv/bin/uvicorn app.main:app --app-dir backend --reload --port 8000
```

The API will be available at `http://localhost:8000` and the OpenAPI docs at
`http://localhost:8000/docs`.

## Run backend tests

```bash
cd /path/to/PACT
source .venv/bin/activate
uv run --project backend --active pytest -q -c backend/pyproject.toml backend/tests
```
