FROM python:3.12-slim
WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
COPY . .
RUN useradd --create-home appuser && mkdir -p runtime && chown -R appuser:appuser /app
EXPOSE 8000
CMD ["python", "entrypoint.py"]
