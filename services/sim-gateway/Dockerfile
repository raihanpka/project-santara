FROM python:3.12-slim

WORKDIR /app
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1

RUN pip install --no-cache-dir uv

COPY libs/sim-kernel /app/libs/sim-kernel
COPY services/sim-gateway /app/services/sim-gateway

RUN uv pip install --system --no-cache \
    /app/libs/sim-kernel \
    /app/services/sim-gateway

EXPOSE 8000
CMD ["uvicorn", "sim_gateway.main:app", "--host", "0.0.0.0", "--port", "8000"]
