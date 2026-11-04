FROM python:3.12-slim
# docker CLI only: the API asks the host's Docker daemon to start sandbox containers
COPY --from=docker:27-cli /usr/local/bin/docker /usr/local/bin/docker
WORKDIR /srv
COPY requirements.txt .
# Optional extra CA (builds behind TLS-intercepting proxies): docker build --secret id=ca,src=/path/ca.crt
RUN --mount=type=secret,id=ca,required=false \
    if [ -f /run/secrets/ca ]; then export PIP_CERT=/run/secrets/ca; fi; pip install --no-cache-dir -r requirements.txt
COPY app ./app
EXPOSE 8000
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000", "--proxy-headers", "--forwarded-allow-ips", "*"]
