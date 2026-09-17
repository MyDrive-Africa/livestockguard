FROM python:3.12-slim

WORKDIR /app

COPY services/mqtt_writer/requirements.txt .
# Increase pip network resilience (slow mirrors / large wheels)
RUN pip install --no-cache-dir --timeout 120 --retries 10 -r requirements.txt

COPY services/mqtt_writer/mqtt_writer.py .
COPY shared/livestockguard_common/ ./livestockguard_common/

ENV PYTHONPATH=/app

CMD ["python", "mqtt_writer.py"]
