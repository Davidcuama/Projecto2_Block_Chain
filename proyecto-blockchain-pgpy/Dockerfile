FROM python:3.11-slim

WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY app/ /app/
COPY keys/ /keys/
ENV PRIVATE_KEY_PATH=/keys/priv.asc
ENV PYTHONUNBUFFERED=1

EXPOSE 8000
CMD ["uvicorn", "main:app", "--host","0.0.0.0","--port","8000"]
