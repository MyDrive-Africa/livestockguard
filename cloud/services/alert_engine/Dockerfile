FROM python:3.12-slim

WORKDIR /app

COPY services/alert_engine/requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY services/alert_engine/app/ ./app/
COPY shared/livestockguard_common/ ./livestockguard_common/

ENV PYTHONPATH=/app

CMD ["python", "-m", "app.main"]
