FROM python:3.12-slim
WORKDIR /app
COPY requirements.txt .
RUN pip install -r requirements.txt
COPY app.py .
COPY static/ ./static/
COPY templates/ ./templates/
# /app/jobs is mounted as a Docker volume so uploaded files persist across rebuilds
RUN mkdir -p /app/jobs
CMD ["gunicorn", "--bind", "0.0.0.0:5000", "app:app"]
