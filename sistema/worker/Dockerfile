FROM python:3.12-slim
ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1 TZ=America/Sao_Paulo
RUN apt-get update && apt-get install -y --no-install-recommends tzdata unar && rm -rf /var/lib/apt/lists/*
WORKDIR /srv
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
COPY app ./app
COPY entrypoint.sh .
RUN chmod +x entrypoint.sh && useradd -u 1000 -m worker
USER worker
EXPOSE 8765 8766
HEALTHCHECK --interval=60s --timeout=5s CMD python -c "import urllib.request;urllib.request.urlopen('http://127.0.0.1:8765/health')"
ENTRYPOINT ["./entrypoint.sh"]
