FROM python:3.12-slim
ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1 PORT=8000 WEB_CONCURRENCY=2
WORKDIR /app
COPY requirements.lock.txt ./requirements.lock.txt
RUN pip install --no-cache-dir -r requirements.lock.txt \
    && groupadd --gid 10001 assistant \
    && useradd --uid 10001 --gid assistant --create-home assistant
COPY --chown=assistant:assistant app ./app
COPY --chown=assistant:assistant data ./data
COPY --chown=assistant:assistant scripts ./scripts
USER assistant
EXPOSE 8000
HEALTHCHECK --interval=30s --timeout=5s --start-period=15s --retries=3 CMD python -c "import os,urllib.request; urllib.request.urlopen('http://127.0.0.1:'+os.getenv('PORT','8000')+'/healthz',timeout=3)"
CMD ["sh", "-c", "exec uvicorn app.main:app --host 0.0.0.0 --port \"${PORT:-8000}\" --workers \"${WEB_CONCURRENCY:-2}\" --proxy-headers --forwarded-allow-ips \"${FORWARDED_ALLOW_IPS:-127.0.0.1}\""]
