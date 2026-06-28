# Artificial Writer service image.
#
# Installs the full service stack (`.[all]`) so the same image can run the API,
# the RQ worker, and the feed scheduler -- the compose file just varies the
# command. The offline CLI/GUI are unaffected; this image is only for the
# multi-tenant web service.
FROM python:3.12-slim

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PIP_NO_CACHE_DIR=1

WORKDIR /app

# Build deps for the wheels that need them (psycopg/bcrypt), removed afterwards.
RUN apt-get update \
    && apt-get install -y --no-install-recommends build-essential libpq-dev \
    && rm -rf /var/lib/apt/lists/*

# Install dependencies first so the layer caches across source-only changes.
COPY pyproject.toml README.md ./
COPY src ./src
RUN pip install ".[all]"

# Migrations + the entrypoint that applies them on start.
COPY alembic.ini ./
COPY migrations ./migrations
COPY infra/entrypoint.sh /usr/local/bin/entrypoint.sh
RUN chmod +x /usr/local/bin/entrypoint.sh

EXPOSE 8000

ENTRYPOINT ["/usr/local/bin/entrypoint.sh"]
CMD ["uvicorn", "artificial_writer.web.app:app", "--host", "0.0.0.0", "--port", "8000"]
