FROM python:3.12-slim
WORKDIR /app

# Install Tesseract OCR (required for Blueprint Hyperlinks tool)
RUN apt-get update && apt-get install -y tesseract-ocr && rm -rf /var/lib/apt/lists/*

COPY requirements.txt .
RUN pip install -r requirements.txt

COPY app.py .
COPY packing_list_engine.py .
COPY static/ ./static/
COPY templates/ ./templates/
COPY BlueprintLinker/ ./BlueprintLinker/

# /app/jobs is mounted as a Docker volume so uploaded files persist across rebuilds
RUN mkdir -p /app/jobs
CMD ["gunicorn", "--bind", "0.0.0.0:5000", "--timeout", "300", "app:app"]
