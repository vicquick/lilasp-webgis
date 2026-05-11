FROM python:3.12-slim

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY app.py .

ENV PYTHONUNBUFFERED=1
ENV AUTH_GATEWAY_BIND=0.0.0.0:5000

EXPOSE 5000

CMD ["python", "-m", "gunicorn", "-b", "0.0.0.0:5000", "--workers", "2", "app:app"]
