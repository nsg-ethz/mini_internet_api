FROM debian:11
RUN apt-get update && apt-get install -y rsyslog locales iputils-ping traceroute \
  openssh-server vim tcpdump net-tools dnsutils iperf3 build-essential smcroute git

# Set locale
RUN sed -i -e 's/# \(en_US\.UTF-8 .*\)/\1/' /etc/locale.gen && \
  locale-gen
ENV LANG=en_US.UTF-8
ENV LANGUAGE=en_US:en
ENV LC_ALL=en_US.UTF-8

# Add startup script and set it as entrypoint
ADD docker-start /usr/sbin/docker-start
RUN chmod +x /usr/sbin/docker-start
RUN git clone https://github.com/troglobit/mtools.git

ENTRYPOINT ["/usr/sbin/docker-start"]
