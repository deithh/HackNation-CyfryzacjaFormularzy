FROM apache/tika:3.3.0.0-full

USER root
RUN apt-get update \
    && apt-get install -y --no-install-recommends tesseract-ocr-pol \
    && rm -rf /var/lib/apt/lists/*

COPY tika-config.xml /tika-config.xml
USER 35002:35002
