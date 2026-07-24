FROM python:3.12-slim

WORKDIR /app

RUN apt-get update && apt-get install -y --no-install-recommends \
    libgeos-dev \
    && rm -rf /var/lib/apt/lists/*

COPY services/api_gateway/requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY services/api_gateway/app/ ./app/
COPY shared/livestockguard_common/ ./livestockguard_common/

ENV PYTHONPATH=/app

EXPOSE 8000

CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
