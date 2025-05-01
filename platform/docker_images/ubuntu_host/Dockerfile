FROM ubuntu:20.04

ENV DEBIAN_FRONTEND=noninteractive

# Install base utilities and dependencies
RUN apt-get update && apt-get install -y \
    curl \
    wget \
    build-essential \
    python3 \
    python3-pip \
    python3-setuptools \
    git \
    libpcap-dev \
    libssl-dev \
    pkg-config \
    python-is-python3 \
    iproute2 \
    iputils-ping \
    iproute2 \
    traceroute \
    net-tools \
    vim \
    openssh-server \
    iperf3 \
    tcpdump \
    rsyslog \
    && rm -rf /var/lib/apt/lists/*

# Install ExaBGP and networking tools
RUN pip install exabgp

RUN apt-get update && apt-get install -y \
    tcpreplay \
    flowgrind \
    mz \
    && rm -rf /var/lib/apt/lists/*

RUN ssh-keygen -A \
    # && sed -i 's/#PasswordAuthentication yes/PasswordAuthentication no/g' /etc/ssh/sshd_config \
    # && sed -i 's/#PrintMotd yes/PrintMotd no/g' /etc/ssh/sshd_config \
    # Unlocks the root user so that ssh login is allowed.
    && sed -i s/root:!/"root:*"/g /etc/shadow \
    && mkdir -p /var/run/sshd /root/.ssh \
    && chmod 0755 /var/run/sshd

# Set ExaBGP environment variables
ENV PATH="/usr/local/bin:${PATH}"
ENV EXABGP_HOME="/usr/local/exabgp"
RUN mkdir -p ${EXABGP_HOME}
ENV EXABGP_LOGLEVEL=INFO
ENV EXABGP_TCP_PORT=179
ENV EXABGP_API=1

# Create a working directory
WORKDIR /root

EXPOSE 22

# Default command
CMD ["/usr/sbin/sshd", "-D", "-e"]
