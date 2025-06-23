FROM python:3.11-slim
WORKDIR /app
COPY . /app

RUN pip install python-telegram-bot==13.11
RUN pip install --no-cache-dir -r requirements.txt

