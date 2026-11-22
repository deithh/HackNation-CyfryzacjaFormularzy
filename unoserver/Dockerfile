FROM alpine:3.24

ARG UNOSERVER_VERSION=3.7

ENV PATH="/opt/venv/bin:$PATH" \
    PYTHONPATH=/usr/lib/libreoffice/program \
    UNO_PATH=/usr/lib/libreoffice/program \
    URE_BOOTSTRAP=vnd.sun.star.pathname:/usr/lib/libreoffice/program/fundamentalrc \
    PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

RUN apk add --no-cache \
        libreoffice-writer \
        libreoffice-calc \
        python3 \
        font-liberation \
        font-carlito \
        font-dejavu \
    && python3 -m venv --system-site-packages /opt/venv \
    && pip install --no-cache-dir "unoserver==${UNOSERVER_VERSION}" \
    && addgroup -S unoserver \
    && adduser -S -G unoserver -h /home/unoserver unoserver

USER unoserver
WORKDIR /home/unoserver
EXPOSE 2003

HEALTHCHECK --interval=10s --timeout=5s --start-period=30s --retries=6 \
    CMD ["unoping", "--host", "127.0.0.1", "--port", "2003"]

CMD ["unoserver", "--interface", "0.0.0.0", "--port", "2003", "--conversion-timeout", "170"]
