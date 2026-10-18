FROM python:3.12-slim

RUN apt-get update \
    && apt-get install -y --no-install-recommends ffmpeg \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /opt/printdash
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY app ./app

ENV PRINTDASH_DATA=/data \
    PYTHONUNBUFFERED=1
EXPOSE 8090

# No proxy headers: the Home Assistant ingress is recognised by its real source
# address (172.30.32.2). Trusting X-Forwarded-For would let anyone pretend to be it.
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8090", "--no-proxy-headers"]
