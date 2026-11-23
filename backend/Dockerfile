FROM python:3.12-slim

ARG PIP_INDEX_URL=https://pypi.org/simple

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1

WORKDIR /app

RUN addgroup --system app && adduser --system --ingroup app app

COPY pyproject.toml alembic.ini ./
COPY app ./app
COPY migrations ./migrations
COPY entrypoint.sh ./entrypoint.sh

RUN pip install --index-url ${PIP_INDEX_URL} . \
    && chmod +x /app/entrypoint.sh \
    && chown -R app:app /app

USER app

EXPOSE 8000

CMD ["sh", "/app/entrypoint.sh"]