FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1

WORKDIR /app

# pygit2 needs libgit2; the git CLI is used for fetch/rev-list.
# Docker access uses the Python docker SDK from requirements.txt (no docker CLI).
RUN apt-get update \
    && apt-get install -y --no-install-recommends libgit2-dev git gcc \
    && rm -rf /var/lib/apt/lists/* \
    && git config --system --add safe.directory '*'

COPY requirements.txt ./
RUN pip install --no-cache-dir -r requirements.txt

COPY . .
RUN mkdir -p /app/data \
    && chmod +x /app/docker-entrypoint.sh

EXPOSE 8000

ENTRYPOINT ["/app/docker-entrypoint.sh"]
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
