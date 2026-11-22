FROM python:3.14-slim AS dependencies
WORKDIR /app

RUN pip install --no-cache-dir poetry==2.1.4 \
    && python -m venv /opt/venv

ENV VIRTUAL_ENV=/opt/venv \
    PATH="/opt/venv/bin:$PATH"

COPY pyproject.toml poetry.lock ./
RUN poetry sync --only main --no-interaction

FROM python:3.14-slim AS runtime
WORKDIR /app

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PATH="/opt/venv/bin:$PATH"

RUN addgroup --system appgroup \
    && adduser --system --ingroup appgroup appuser \
    && apt-get update \
    && apt-get install -y --no-install-recommends libmagic1 \
    && rm -rf /var/lib/apt/lists/*

COPY --from=dependencies /opt/venv /opt/venv

COPY logging.json .
COPY app ./app
RUN chown -R appuser:appgroup /app

USER appuser
EXPOSE 8080

CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8080", "--log-config", "logging.json"]
