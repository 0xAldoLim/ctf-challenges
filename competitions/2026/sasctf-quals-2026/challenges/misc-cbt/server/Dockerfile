FROM python:3.14-slim

ENV PYTHONUNBUFFERED=1

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY app/ ./app/

RUN useradd --create-home --uid 1000 schizo \
    && mkdir -p /app/hostkeys \
    && chown schizo:schizo /app/hostkeys
USER schizo

EXPOSE 2222

CMD ["python", "-u", "app/ssh_server.py"]
