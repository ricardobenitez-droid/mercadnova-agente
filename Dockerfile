FROM python:3.12-slim
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    GRADIO_SERVER_NAME=0.0.0.0 \
    GRADIO_SERVER_PORT=7860
WORKDIR /app
RUN useradd \
    --create-home \
    --uid 10001 \
    appuser
COPY requirements.txt .
RUN python -m pip install --upgrade pip && \
    python -m pip install -r requirements.txt
COPY --chown=appuser:appuser . .
USER appuser
EXPOSE 7860
HEALTHCHECK \
    --interval=30s \
    --timeout=10s \
    --start-period=60s \
    --retries=3 \
    CMD python -c \
    "import urllib.request; \
    urllib.request.urlopen(\
    'http://127.0.0.1:7860/', \
    timeout=5)"
CMD ["python", "app.py"]