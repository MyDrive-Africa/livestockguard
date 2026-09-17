FROM python:3.12-slim

WORKDIR /app

COPY services/alert_engine/requirements.txt .
# Increase pip network resilience (slow mirrors / large wheels like firebase-admin)
RUN pip install --no-cache-dir --timeout 120 --retries 10 -r requirements.txt

COPY services/alert_engine/app/ ./app/
COPY shared/livestockguard_common/ ./livestockguard_common/

ENV PYTHONPATH=/app

CMD ["python", "-m", "app.main"]
