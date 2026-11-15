FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PYTHONPATH=/app/backend:/app

WORKDIR /app

COPY backend/requirements.txt /app/backend/requirements.txt
RUN python -m pip install --no-cache-dir --disable-pip-version-check -r /app/backend/requirements.txt

RUN useradd --system --create-home --uid 10001 app

COPY --chown=10001:10001 backend/app /app/backend/app
COPY --chown=10001:10001 datascience/__init__.py datascience/evapotranspiration.py datascience/power.py datascience/power_parameters.py datascience/soilgrids.py /app/datascience/
COPY --chown=10001:10001 data/reference /app/data/reference
COPY --chown=10001:10001 data/processed/power /app/data/processed/power
COPY --chown=10001:10001 data/processed/soil /app/data/processed/soil
COPY --chown=10001:10001 shared/fixtures /app/shared/fixtures

USER 10001:10001

EXPOSE 8000

HEALTHCHECK --interval=30s --timeout=5s --start-period=10s --retries=3 \
    CMD python -c "import os, urllib.request; urllib.request.urlopen('http://127.0.0.1:' + os.getenv('PORT', '8000') + '/health', timeout=3)"

CMD ["sh", "-c", "uvicorn app.main:app --app-dir /app/backend --host 0.0.0.0 --port ${PORT:-8000}"]
