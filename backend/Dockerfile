FROM python:3.12-slim

WORKDIR /app
COPY pyproject.toml ./
COPY app ./app
COPY config ./config
COPY db ./db
COPY sql ./sql
RUN pip install --no-cache-dir .

ENV PORT=8000 \
    AUTH_MODE=demo \
    DATA_PATH=/tmp/store.json \
    HUNYUAN_ENABLED=false \
    TONGYI_ENABLED=false \
    SES_MODE=mock \
    WECHAT_PAY_MODE=disabled \
    CORS_ORIGINS=https://pickglobal.mornscience.top
EXPOSE 8000
HEALTHCHECK --interval=30s --timeout=5s --start-period=20s CMD python -c "import os,urllib.request; urllib.request.urlopen('http://127.0.0.1:%s/api/v1/health/live' % os.environ.get('PORT','8000'))"
CMD ["sh", "-c", "uvicorn app.main:app --host 0.0.0.0 --port ${PORT:-8000}"]
