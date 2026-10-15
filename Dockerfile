FROM python:3.12-slim

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PYTHONPATH=/app/src \
    MPLBACKEND=Agg \
    MPLCONFIGDIR=/tmp/matplotlib \
    PORT=10000 \
    OMP_NUM_THREADS=1 \
    OPENBLAS_NUM_THREADS=1

WORKDIR /app
COPY deploy/requirements.txt /app/deploy/requirements.txt
RUN pip install --no-cache-dir -r deploy/requirements.txt

COPY src /app/src
COPY config /app/config
COPY assets /app/assets
COPY data /app/data
# The repository includes the built dashboard and its legacy panel assets.
COPY frontend/dist /app/frontend/dist
COPY deploy/api.render.yaml /app/config/api.yaml

RUN useradd --create-home --uid 10001 stockai \
    && mkdir -p /app/reports /app/data/api_cache /app/data/intraday \
    && chown -R stockai:stockai /app/data /app/reports
USER stockai

EXPOSE 10000
CMD ["sh", "-c", "exec uvicorn stockai.api.app:app --host 0.0.0.0 --port \"${PORT:-10000}\" --workers 1 --no-proxy-headers"]
