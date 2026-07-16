FROM python:3.12-slim

WORKDIR /srv/app

RUN pip install --no-cache-dir uv

COPY pyproject.toml README.md ./
COPY app ./app
COPY migrations ./migrations
COPY alembic.ini ./
COPY knowledge_base ./knowledge_base
COPY scripts ./scripts

RUN uv pip install --system .

EXPOSE 8000
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
