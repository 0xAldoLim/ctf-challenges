FROM python:3.12-alpine

RUN apk add --no-cache bind-tools iproute2

WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY bot.py .

CMD ["python", "-u", "bot.py"]
