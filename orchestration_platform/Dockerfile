FROM python:3.12-bookworm

RUN apt-get update && \
    apt-get install -y wget curl ca-certificates gnupg graphviz graphviz-dev clang iproute2 iputils-ping traceroute tcpdump nano docker.io


RUN pip install "fastapi[standard]" pydantic-settings docker
RUN groupadd -g 988 docker_group && \
useradd -u 1000 -g docker_group docker_user && \
usermod -aG docker_group docker_user
# Switch to the created user
USER docker_user


WORKDIR /app


ENTRYPOINT ["python3", "app.py"]
# ENTRYPOINT ["tail", "-f", "/dev/null"]
