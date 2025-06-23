FROM python:3.11-slim
WORKDIR /app
COPY . .

RUN pip install python-telegram-bot==13.11
RUN pip install --no-cache-dir -r requirements.txt

CMD ["python3", "bot/tat.py"]
