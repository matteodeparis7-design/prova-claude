FROM python:3.12-slim

# ffmpeg per i video, Tesseract (con l'italiano) per controllare i prezzi dei volantini fatti di immagini.
RUN apt-get update \
 && apt-get install -y --no-install-recommends ffmpeg tesseract-ocr tesseract-ocr-ita \
 && rm -rf /var/lib/apt/lists/*

WORKDIR /app
COPY pyproject.toml README.md ./
COPY promovo ./promovo
RUN pip install --no-cache-dir .

ENV PROMOVO_DATA_DIR=/data \
    PROMOVO_DATABASE_URL=sqlite:////data/promovo.db \
    PORT=8000
RUN mkdir -p /data
VOLUME ["/data"]
EXPOSE 8000

# PROMOVO_DEMO=1 crea l'account di prova (demo@promovo.it / promovo2026).
CMD ["sh", "-c", "python -m promovo --host 0.0.0.0 --port ${PORT} ${PROMOVO_DEMO:+--demo}"]
