FROM python:3.13-slim
WORKDIR /app
COPY requirements.txt /app/status_service/requirements.txt
RUN pip install --no-cache-dir -r /app/status_service/requirements.txt
COPY . /app/status_service
ENV PORT=8080
CMD ["gunicorn", "--bind", "0.0.0.0:8080", "--workers", "1", "status_service.app:app"]
