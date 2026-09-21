FROM python:3.12-slim
ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1 UV_LINK_MODE=copy
RUN apt-get update && apt-get install -y --no-install-recommends tesseract-ocr tesseract-ocr-eng libglib2.0-0 && rm -rf /var/lib/apt/lists/*
RUN pip install --no-cache-dir uv==0.8.22
WORKDIR /workspace
COPY backend/pyproject.toml backend/uv.lock ./backend/
RUN cd backend && uv sync --frozen --no-dev --no-install-project
COPY backend ./backend
COPY prompts ./prompts
COPY shared/schemas ./shared/schemas
RUN cd backend && uv sync --frozen --no-dev
RUN useradd --create-home app && chown -R app:app /workspace
USER app
WORKDIR /workspace/backend
ENV PATH="/workspace/backend/.venv/bin:$PATH"
EXPOSE 8000
# The API and the background worker (which reads documents and runs the checks) run in one
# container so a single Railway service is a complete deployment. The worker is restarted if it
# exits. Set RUN_WORKER=false to run the API alone and start the worker as its own service
# (`python -m app.workers.runner`), as docker/compose.dev.yml does. Extra workers are safe: they
# share the job queue through PostgreSQL row locks.
ENV RUN_WORKER=true
# Jobs are limited by database round trips, not CPU, so a few run at once. Each slot uses about two
# database connections and the hosted database allows 60, so raise this only with that in mind.
ENV WORKER_CONCURRENCY=4
CMD ["sh", "-c", "if [ \"$RUN_WORKER\" = \"true\" ]; then (while true; do python -m app.workers.runner; echo 'worker exited; restarting in 5 seconds' >&2; sleep 5; done) & fi; exec uvicorn app.main:app --host 0.0.0.0 --port ${PORT:-8000}"]
