FROM python:3.12-slim
WORKDIR /app
COPY pyproject.toml README.md LICENSE ./
COPY src ./src
RUN SETUPTOOLS_SCM_PRETEND_VERSION=1.3.0.dev0 pip install --no-cache-dir .
RUN --mount=type=cache,target=/root/.cache/pip pip install torch==2.15.0 --index-url https://download.pytorch.org/whl/cpu
COPY apps/backend/requirements.txt .
COPY apps/backend/requirements-dialog.txt .
RUN --mount=type=cache,target=/root/.cache/pip pip install -r requirements-dialog.txt
COPY apps/backend/ .
CMD ["uvicorn", "voice_api.main:app", "--host", "0.0.0.0", "--port", "8000", "--ws-max-size", "16384"]
