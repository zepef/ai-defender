FROM python:3.12-slim AS builder

WORKDIR /build
COPY requirements.txt .
RUN pip install --no-cache-dir --prefix=/install -r requirements.txt

FROM python:3.12-slim

RUN groupadd -r honeypot && useradd -r -g honeypot -d /app -s /sbin/nologin honeypot

WORKDIR /app

COPY --from=builder /install /usr/local
COPY shared/ shared/
COPY honeypot/ honeypot/

RUN mkdir -p /data && chown honeypot:honeypot /data

USER honeypot

ENV HONEYPOT_DB_PATH=/data/honeypot.db
ENV HONEYPOT_HOST=0.0.0.0
ENV HONEYPOT_PORT=5000

EXPOSE 5000

HEALTHCHECK --interval=30s --timeout=5s --start-period=5s --retries=3 \
    CMD python -c "import urllib.request; urllib.request.urlopen('http://localhost:5000/health')" || exit 1

CMD ["gunicorn", "--bind", "0.0.0.0:5000", "--workers", "2", "--threads", "4", "--timeout", "310", "--worker-class", "gthread", "honeypot.app:create_app()"]
