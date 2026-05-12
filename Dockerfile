FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PORT=5000

WORKDIR /app

RUN useradd --create-home --uid 1000 app \
 && mkdir -p /app/cache \
 && chown -R app:app /app

COPY --chown=app:app requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY --chown=app:app app.py favicon.ico ./
COPY --chown=app:app templates ./templates
COPY --chown=app:app static ./static

USER app

EXPOSE 5000

CMD ["python", "app.py"]
