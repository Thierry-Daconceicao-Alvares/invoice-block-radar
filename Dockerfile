# The API only: it serves the files in data/demo, models/ and docs/results.
FROM python:3.13-slim
RUN apt-get update && apt-get install -y --no-install-recommends libgomp1 && rm -rf /var/lib/apt/lists/*
WORKDIR /app
COPY requirements-api.txt .
RUN pip install --no-cache-dir -r requirements-api.txt
COPY radar ./radar
COPY api ./api
COPY models ./models
COPY data/demo ./data/demo
COPY docs/results ./docs/results
ENV PORT=8000
EXPOSE 8000
CMD ["sh", "-c", "uvicorn api.main:app --host 0.0.0.0 --port ${PORT}"]
