FROM python:3.10-slim

WORKDIR /app

COPY src/ /app/
RUN pip install --no-cache-dir -r /app/requirements.txt

ENV PYTHONUNBUFFERED=1

CMD ["python", "app.py"]