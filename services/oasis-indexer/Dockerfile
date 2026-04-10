FROM python:3.11-slim

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

# /repos is mounted at runtime with the repositories to index
VOLUME ["/repos"]

CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8002"]
