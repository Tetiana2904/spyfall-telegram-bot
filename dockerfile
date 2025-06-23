FROM python:3.11-slim

WORKDIR /app
COPY . /app

# 🔒 Спочатку ставимо правильну версію бібліотеки Telegram
RUN pip install --no-cache-dir python-telegram-bot==13.15

# 🔁 Потім решта (не має перезаписати стару версію)
RUN pip install --no-cache-dir -r requirements.txt

CMD ["python3", "bot/tat.py"]