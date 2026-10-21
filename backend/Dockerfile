FROM python:3.12-slim
ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1
WORKDIR /app
COPY pyproject.toml requirements.lock ./
RUN pip install --no-cache-dir -r requirements.lock && useradd --create-home --uid 10001 milio && mkdir /data && chown milio /data
COPY . .
RUN pip install --no-cache-dir --no-deps .
ENV RUFF_CACHE_DIR=/tmp/milio-ruff-cache MYPY_CACHE_DIR=/tmp/milio-mypy-cache PYTEST_ADDOPTS="-p no:cacheprovider"
USER milio
EXPOSE 8000
CMD ["uvicorn", "app.main:create_app", "--factory", "--host", "0.0.0.0", "--port", "8000"]
