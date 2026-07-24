# Образ для деплоя панели (Railway / Render / любой Docker-хост).
FROM python:3.11-slim

WORKDIR /app

# Сначала зависимости — лучше кешируется
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

# Хостинг передаёт порт в $PORT; локально — 8501
ENV PORT=8501
EXPOSE 8501

# Shell-форма, чтобы подставился $PORT
CMD streamlit run app.py --server.port ${PORT:-8501} --server.address 0.0.0.0 --server.headless true
