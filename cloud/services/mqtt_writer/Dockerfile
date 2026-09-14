FROM python:3.12-slim

WORKDIR /app

COPY services/mqtt_writer/requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY services/mqtt_writer/mqtt_writer.py .
COPY shared/livestockguard_common/ ./livestockguard_common/

ENV PYTHONPATH=/app

CMD ["python", "mqtt_writer.py"]
