FROM python:3.12-slim

WORKDIR /app

COPY requirements.txt .
# Increase pip network resilience (slow mirrors / large wheels like numpy)
RUN pip install --no-cache-dir --timeout 120 --retries 10 -r requirements.txt

COPY app/ ./app/

CMD ["python", "-m", "app.main"]
