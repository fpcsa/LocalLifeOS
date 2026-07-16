FROM python:3.12-slim@sha256:c3d81d25b3154142b0b42eb1e61300024426268edeb5b5a26dd7ddf64d9daf28

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1

WORKDIR /workspace/apps/api

COPY apps/api/requirements.txt ./requirements.txt
RUN pip install --no-cache-dir -r requirements.txt

COPY apps/api/ ./
COPY data/demo/attachments/ ./demo-assets/
COPY apps/api/docker-entrypoint.sh /usr/local/bin/locallife-api-entrypoint

RUN addgroup --system locallife \
    && adduser --system --ingroup locallife locallife \
    && mkdir -p /workspace/data \
    && chown -R locallife:locallife /workspace \
    && chmod 0755 /usr/local/bin/locallife-api-entrypoint

EXPOSE 8000

ENTRYPOINT ["/usr/local/bin/locallife-api-entrypoint"]
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000", "--no-access-log"]
