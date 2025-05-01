#!/bin/bash

# MOD_STATISTIC="-m statistic --mode random --probability 0.1"
# NFLOG_CONFIG="--nflog-group 5 --nflog-prefix SFLOW"

# # ipv4
# iptables -I INPUT -p udp ! --dport 3784 -j NFLOG $MOD_STATISTIC $NFLOG_CONFIG
# iptables -I INPUT -p tcp -j NFLOG $MOD_STATISTIC $NFLOG_CONFIG
# iptables -I INPUT -p gre -j NFLOG $MOD_STATISTIC $NFLOG_CONFIG
# iptables -I INPUT -p 41 -j NFLOG $MOD_STATISTIC $NFLOG_CONFIG
# iptables -I FORWARD -p udp ! --dport 3784 -j NFLOG $MOD_STATISTIC $NFLOG_CONFIG
# iptables -I FORWARD -p tcp -j NFLOG $MOD_STATISTIC $NFLOG_CONFIG
# iptables -I FORWARD -p gre -j NFLOG $MOD_STATISTIC $NFLOG_CONFIG
# iptables -I FORWARD -p 41 -j NFLOG $MOD_STATISTIC $NFLOG_CONFIG
# iptables -I OUTPUT -p udp ! --dport 3784 -j NFLOG $MOD_STATISTIC $NFLOG_CONFIG
# iptables -I OUTPUT -p tcp -j NFLOG $MOD_STATISTIC $NFLOG_CONFIG
# iptables -I OUTPUT -p gre -j NFLOG $MOD_STATISTIC $NFLOG_CONFIG
# iptables -I OUTPUT -p 41 -j NFLOG $MOD_STATISTIC $NFLOG_CONFIG

# # ipv6
# ip6tables -I INPUT -p udp ! --dport 3784 -j NFLOG $MOD_STATISTIC $NFLOG_CONFIG
# ip6tables -I INPUT -p tcp -j NFLOG $MOD_STATISTIC $NFLOG_CONFIG
# ip6tables -I INPUT -p gre -j NFLOG $MOD_STATISTIC $NFLOG_CONFIG
# ip6tables -I INPUT -p 41 -j NFLOG $MOD_STATISTIC $NFLOG_CONFIG
# ip6tables -I FORWARD -p udp ! --dport 3784 -j NFLOG $MOD_STATISTIC $NFLOG_CONFIG
# ip6tables -I FORWARD -p tcp -j NFLOG $MOD_STATISTIC $NFLOG_CONFIG
# ip6tables -I FORWARD -p gre -j NFLOG $MOD_STATISTIC $NFLOG_CONFIG
# ip6tables -I FORWARD -p 41 -j NFLOG $MOD_STATISTIC $NFLOG_CONFIG
# ip6tables -I OUTPUT -p udp ! --dport 3784 -j NFLOG $MOD_STATISTIC $NFLOG_CONFIG
# ip6tables -I OUTPUT -p tcp -j NFLOG $MOD_STATISTIC $NFLOG_CONFIG
# ip6tables -I OUTPUT -p gre -j NFLOG $MOD_STATISTIC $NFLOG_CONFIG
# ip6tables -I OUTPUT -p 41 -j NFLOG $MOD_STATISTIC $NFLOG_CONFIG

# sFlow
hsflowd -f /etc/hsflowd.conf -d &
