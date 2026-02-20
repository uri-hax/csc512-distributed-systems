FROM python:3.14-slim

ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1

# Install dependencies
COPY requirements.txt ./
RUN if [ -s requirements.txt ]; then pip install --no-cache-dir -r requirements.txt; fi

WORKDIR /service

# Copy application
COPY . ./

# Default submissions root (can be overridden at runtime)
ENV SUBMISSIONS_ROOT=/student
RUN mkdir -p ${SUBMISSIONS_ROOT} || true

RUN chmod +x /service/serve.sh || true
ENTRYPOINT ["/service/serve.sh"]