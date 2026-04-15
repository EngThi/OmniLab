FROM python:3.11-slim

RUN apt-get update && apt-get install -y \
    chromium chromium-driver \
    fonts-liberation libatk-bridge2.0-0 libgtk-3-0 \
    libnss3 libxss1 libgbm1 && \
    rm -rf /var/lib/apt/lists/*

WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
RUN python -m playwright install chromium --with-deps

COPY . .
EXPOSE 8000
CMD ["python", "server.py"]
