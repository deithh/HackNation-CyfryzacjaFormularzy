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
    PATH="/opt/venv/bin:$PATH" \
    FLASK_PORT=5000

RUN addgroup --system appgroup \
    && adduser --system --ingroup appgroup appuser

COPY --from=dependencies /opt/venv /opt/venv

COPY app ./app
RUN mkdir -p /tmp/form-viewer-results \
    && chown -R appuser:appgroup /app /tmp/form-viewer-results

USER appuser
EXPOSE 5000

CMD ["sh", "-c", "exec gunicorn --bind 0.0.0.0:${FLASK_PORT:-5000} --workers 2 --no-control-socket --timeout ${REQUEST_TIMEOUT_SECONDS:-1800} app:app"]
