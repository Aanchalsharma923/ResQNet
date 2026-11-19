# ResQNet Production Container
FROM python:3.12-slim

WORKDIR /app

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    RESQNET_HOST=0.0.0.0 \
    RESQNET_PORT=8000 \
    RESQNET_EVENT_BIND_HOST=0.0.0.0

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY resqnet/ ./resqnet/
COPY configs/ ./configs/
COPY scripts/ ./scripts/

EXPOSE 8000/tcp
EXPOSE 50099/udp
EXPOSE 50010-50014/udp
EXPOSE 51010-51014/udp

CMD ["uvicorn", "resqnet.backend.app.main:app", "--host", "0.0.0.0", "--port", "8000"]
