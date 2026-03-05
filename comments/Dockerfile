FROM ollama/ollama:latest

RUN apt-get update && \
    apt-get install -y python3 python3-pip python3-venv && \
    rm -rf /var/lib/apt/lists/*

RUN python3 -m venv /opt/venv
ENV PATH="/opt/venv/bin:$PATH"
ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1
ENV SUBMISSIONS_ROOT=/student

WORKDIR /service

COPY requirements.txt ./
RUN if [ -s requirements.txt ]; then pip3 install --no-cache-dir -r requirements.txt; fi

COPY . ./
RUN mkdir -p ${SUBMISSIONS_ROOT} || true
RUN chmod +x /service/serve.sh || true

EXPOSE 80 11434

ENTRYPOINT ["/service/serve.sh"]