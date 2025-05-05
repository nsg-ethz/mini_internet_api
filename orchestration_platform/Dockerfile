FROM python:3.12-bookworm

RUN apt-get update && \
    apt-get install -y wget curl ca-certificates gnupg graphviz graphviz-dev clang iproute2 iputils-ping traceroute tcpdump nano docker.io

RUN export PYTHONPATH=/app/netfabric/src/


RUN wget https://github.com/bazelbuild/bazelisk/releases/download/v1.25.0/bazelisk-amd64.deb -O /tmp/bazelisk.deb && \
    dpkg -i /tmp/bazelisk.deb && \
    rm /tmp/bazelisk.deb

RUN pip install "fastapi[standard]" pydantic-settings docker
RUN groupadd -g 988 docker_group && \
useradd -u 1000 -g docker_group docker_user && \
usermod -aG docker_group docker_user
# Switch to the created user
USER docker_user

# EXPOSE 5432

WORKDIR /app


ENTRYPOINT ["python3", "app.py"]
# ENTRYPOINT ["tail", "-f", "/dev/null"]
