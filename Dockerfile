FROM python:3.13-slim
WORKDIR /app

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

COPY pyproject.toml README.md ./
COPY src ./src
RUN pip install --no-cache-dir .

USER nobody
EXPOSE 8080

CMD ["uvicorn", "blueprint_ai.main:create_app", "--factory", "--host", "0.0.0.0", "--port", "8080"]
