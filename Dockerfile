FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

WORKDIR /app
COPY requirements.txt pyproject.toml VERSION ./
RUN pip install --no-cache-dir -r requirements.txt
COPY app ./app
COPY web ./web

EXPOSE 8765
CMD ["python", "-m", "app.main"]
