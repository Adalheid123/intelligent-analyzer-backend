FROM python:3.11-slim

WORKDIR /app

COPY requirements.txt .
RUN pip install --upgrade pip setuptools wheel && pip install -r requirements.txt

COPY . .

ENV PORT=5000
EXPOSE 5000

CMD gunicorn app:app --bind 0.0.0.0:5000 --workers 2 --timeout 120
