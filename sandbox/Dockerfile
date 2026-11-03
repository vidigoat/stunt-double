# The rehearsal sandbox: minimal Python, no network tools, non-root, harness baked in.
FROM python:3.12-slim
RUN useradd --uid 10001 --no-create-home --shell /usr/sbin/nologin double \
 && rm -rf /usr/bin/apt* /usr/bin/dpkg* /var/lib/apt /var/cache/apt
COPY api/app/harness/runner.py /harness/runner.py
USER 10001
WORKDIR /work
# env -i: the plan starts with an EMPTY environment - no inherited variables, no secrets.
ENTRYPOINT ["/usr/bin/env", "-i", "PATH=/usr/local/bin:/usr/bin:/bin", "HOME=/tmp", "python", "-I", "-B", "/harness/runner.py"]
