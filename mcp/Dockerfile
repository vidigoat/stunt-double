FROM python:3.12-slim
WORKDIR /srv
COPY requirements.txt .
RUN --mount=type=secret,id=ca,required=false \
    if [ -f /run/secrets/ca ]; then export PIP_CERT=/run/secrets/ca; fi; pip install --no-cache-dir -r requirements.txt
COPY server.py .
EXPOSE 8001
CMD ["python", "server.py", "--http", "--host", "0.0.0.0", "--port", "8001"]
