FROM python:3.12-slim

WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
COPY app.py .

ENV DATABASE_URL="postgresql://admin:s3cret-passw0rd@db:5432/myapp"
ENV API_KEY="AKIAIOSFODNN7EXAMPLE"
ENV SECRET_TOKEN="Bearer eyJhbGciOiJIUzI1NiJ9.eyJ1c2VyIjoiYWRtaW4ifQ.SflKxwRJ"

EXPOSE 5000

CMD ["python", "app.py"]
