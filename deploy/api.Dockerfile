# FastAPI backend + DuckDB warehouse. Builds natively on ARM (Oracle Ampere) and x86.
FROM python:3.12-slim

ENV PYTHONUNBUFFERED=1 \
    PYTHONUTF8=1 \
    PIP_NO_CACHE_DIR=1 \
    COMPETE_DATA_DIR=/data \
    COMPETE_DUCKDB_PATH=/data/compete.duckdb \
    PYTHONPATH=/app

# build-essential covers any dependency without a prebuilt ARM wheel.
RUN apt-get update \
 && apt-get install -y --no-install-recommends build-essential curl \
 && rm -rf /var/lib/apt/lists/*

WORKDIR /app
COPY requirements.txt .
RUN pip install -r requirements.txt
# Pre-install the DuckDB extensions dbt uses, so first boot never depends on
# downloading them at runtime.
RUN python -c "import duckdb; c = duckdb.connect(); [c.install_extension(e) for e in ('httpfs', 'json')]"

COPY . .

VOLUME ["/data"]
EXPOSE 8000

HEALTHCHECK --interval=30s --timeout=5s --start-period=600s --retries=5 \
  CMD curl -fsS http://127.0.0.1:8000/api/health || exit 1

# First boot on an empty /data seeds demo data, builds marts and loads the
# captured snapshots (see api/main.py::_autoseed_if_empty). One worker: DuckDB
# allows a single writer process.
CMD ["uvicorn", "api.main:app", "--host", "0.0.0.0", "--port", "8000", "--proxy-headers", "--forwarded-allow-ips", "*"]
