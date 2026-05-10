FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PORT=5000

WORKDIR /app

RUN useradd --create-home --uid 1000 app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY app.py favicon.ico ./
COPY templates ./templates

USER app

EXPOSE 5000

CMD ["python", "app.py"]
