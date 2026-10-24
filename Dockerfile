FROM python:3.12-slim
WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
COPY newsml ./newsml
COPY tests ./tests
RUN useradd --uid 10001 --create-home appuser && mkdir -p /app/artifacts /app/logs && chown -R appuser:appuser /app
USER appuser
EXPOSE 8000
HEALTHCHECK --interval=30s --timeout=5s --start-period=20s CMD python -c "import urllib.request; urllib.request.urlopen('http://127.0.0.1:8000/health',timeout=3)" || exit 1
CMD ["python", "-m", "newsml.server", "--host", "0.0.0.0"]
