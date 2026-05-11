FROM python:3.12-slim

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY app.py .

ENV PYTHONUNBUFFERED=1 \
    AUTH_GATEWAY_BIND=0.0.0.0:5000

EXPOSE 5000

# python:3.12-slim has no `wget` / `curl` — use python urllib for the
# healthcheck. Exit 0 only on HTTP 200.
HEALTHCHECK --interval=30s --timeout=5s --retries=5 \
  CMD python -c "import urllib.request,sys; r=urllib.request.urlopen('http://127.0.0.1:5000/health',timeout=3); sys.exit(0 if r.status==200 else 1)" || exit 1

CMD ["python", "-m", "gunicorn", "-b", "0.0.0.0:5000", "--workers", "2", "app:app"]
