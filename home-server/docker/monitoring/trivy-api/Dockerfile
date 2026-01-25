FROM python:3.11-alpine

WORKDIR /app

RUN pip install --no-cache-dir flask gunicorn

COPY app.py .

EXPOSE 8080

CMD ["gunicorn", "-w", "2", "-b", "0.0.0.0:8080", "app:app"]
