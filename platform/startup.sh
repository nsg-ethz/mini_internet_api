#!/bin/bash
#
# starts once specific "lab" mini-Internet

# set -x
set -o errexit # exit on error
set -o pipefail # catch errors in pipelines
set -o nounset # exit on undeclared variable

# Default values
disable_mpls=false

# Function to display usage
usage() {
    echo "Usage: ${0##*/} [--disable-mpls] lab_type" 2>&1
    exit 1
}

# Parse options
OPTIONS=$(getopt -o "" --long disable-mpls -- "$@")
if [ $? -ne 0 ]; then
    usage
fi
eval set -- "$OPTIONS"

while true; do
    case "$1" in
        --disable-mpls ) disable_mpls=true; shift ;;
        -- ) shift; break ;;
        * ) usage ;;
    esac
done

if [ "$#" != 1 ]; then
  echo "usage: ${0##*/} lab_type" 2>&1
  exit 1
fi

# Check for programs we'll need.
search_path () {
    # display the path to the command
    type -p "$1" > /dev/null && return 0
    echo >&2 "$0: $1 not found in \$PATH, please install and try again"
    exit 1
}

if (($UID != 0)); then
    echo "$0 needs to be run as root"
    exit 1
fi

# change size of ARP table necessary for large networks
sysctl net.ipv4.neigh.default.gc_thresh1=16384
sysctl net.ipv4.neigh.default.gc_thresh2=32768
sysctl net.ipv4.neigh.default.gc_thresh3=131072
echo 256 | sudo tee /proc/sys/fs/inotify/max_user_instances
sysctl -p

# Increase the max number of running processes
sysctl kernel.pid_max=4194304

# Load MPLS kernel modules
modprobe mpls_router
modprobe mpls_gso
modprobe mpls_iptunnel
modprobe ip6_tables

search_path ovs-vsctl
search_path docker
search_path uuidgen

# netns: used to create isolated network environments/namespaces
if (ip netns) > /dev/null 2>&1; then :; else
    echo >&2 "${0##*/}: ip utility not found (or it does not support netns),"\
             "cannot proceed"
    exit 1
fi

# TODO: check the directory is platform/
DIRECTORY=$(cd `dirname $0` && pwd)
DIRECTORY="${DIRECTORY}"/labs

if [ ! -d "${DIRECTORY}"/"$1" ]; then
    echo "given lab type does not exist: $1"
    exit 1
fi

echo "$(date +%Y-%m-%d_%H-%M-%S)"

if [ -d "${DIRECTORY}"/config ]; then
    echo "cleanup.sh based on currently running local config"
    # echo ./cleanup/cleanup.sh "${DIRECTORY}"
    time ./cleanup/cleanup.sh "${DIRECTORY}"
    time ./cleanup/cleanup.sh "${DIRECTORY}"

    echo ""
    echo ""

    sleep 1

    rm -r "${DIRECTORY}"/config
fi

# copying the relevant config for the selected lab
cp -r "${DIRECTORY}"/"${1}" "${DIRECTORY}"/config

echo "cleanup.sh attempt based on new lab, in case someone else has it running"
time ./cleanup/cleanup.sh "${DIRECTORY}"
time ./cleanup/cleanup.sh "${DIRECTORY}"

echo ""
echo ""

sleep 1

echo "folder_setup.sh $(($(date +%s%N)/1000000))" > "${DIRECTORY}"/log.txt
echo "folder_setup.sh: "
time ./setup/folder_setup.sh "${DIRECTORY}"

echo ""
echo ""

echo "dns_config.sh $(($(date +%s%N)/1000000))" >> "${DIRECTORY}"/log.txt
echo "dns_config.sh: "
time ./setup/dns_config.sh "${DIRECTORY}"

echo ""
echo ""

# echo "rpki_config.sh $(($(date +%s%N)/1000000))" >> "${DIRECTORY}"/log.txt
# echo "rpki_config.sh: "
# time ./setup/rpki_config.sh "${DIRECTORY}"

# echo ""
# echo ""

# echo "vpn_config.sh $(($(date +%s%N)/1000000))" >> "${DIRECTORY}"/log.txt
# echo "vpn_config.sh: "
# time ./setup/vpn_config.sh "${DIRECTORY}"

# echo ""
# echo ""

# echo "goto_scripts.sh $(($(date +%s%N)/1000000))" >> "${DIRECTORY}"/log.txt
# echo "goto_scripts.sh: "
# time ./setup/goto_scripts.sh "${DIRECTORY}"

# echo ""
# echo ""

# echo "save_configs.sh $(($(date +%s%N)/1000000))" >> "${DIRECTORY}"/log.txt
# echo "save_configs.sh: "
# time ./setup/save_configs.sh "${DIRECTORY}"

# echo ""
# echo ""

echo "container_setup.sh $(($(date +%s%N)/1000000))" >> "${DIRECTORY}"/log.txt
echo "container_setup.sh: "
time ./setup/container_setup.sh "${DIRECTORY}"

echo ""
echo ""

echo "connect_l3_host_router.sh $(($(date +%s%N)/1000000))" >> "${DIRECTORY}"/log.txt
echo "connect_l3_host_router.sh: "
time ./setup/connect_l3_host_router.sh "${DIRECTORY}"

echo ""
echo ""

echo "connect_l2_network.sh $(($(date +%s%N)/1000000))" >> "${DIRECTORY}"/log.txt
echo "connect_l2_network.sh: "
time ./setup/connect_l2_network.sh "${DIRECTORY}"

echo ""
echo ""

echo "connect_internal_routers.sh $(($(date +%s%N)/1000000))" >> "${DIRECTORY}"/log.txt
echo "connect_internal_routers.sh: "
time ./setup/connect_internal_routers.sh "${DIRECTORY}"

echo ""
echo ""

echo "connect_external_routers.sh $(($(date +%s%N)/1000000))" >> "${DIRECTORY}"/log.txt
echo "connect_external_routers.sh: "
time ./setup/connect_external_routers.sh "${DIRECTORY}"

echo ""
echo ""

echo "connect_services.sh $(($(date +%s%N)/1000000))" >> "${DIRECTORY}"/log.txt
echo "connect_services.sh: "
time ./setup/connect_services.sh "${DIRECTORY}"

echo ""
echo ""

echo "layer2_config.sh: "
echo "layer2_config.sh $(($(date +%s%N)/1000000))" >> "${DIRECTORY}"/log.txt
time ./setup/layer2_config.sh "${DIRECTORY}"

echo ""
echo ""

if [[ "$1" == "mpls" ]]; then
    echo "mpls_setup.sh: "
    echo "mpls_setup.sh $(($(date +%s%N)/1000000))" >> "${DIRECTORY}"/log.txt
    time ./setup/mpls_setup.sh "${DIRECTORY}"

    echo ""
    echo ""
fi

echo "router_config.sh: "
echo "router_config.sh $(($(date +%s%N)/1000000))" >> "${DIRECTORY}"/log.txt
time ./setup/router_config.sh "${DIRECTORY}"

echo ""
echo ""

# echo "Waiting 60sec for RPKI CA and proxy to startup.."
# sleep 60

# echo "rpki_setup.sh $(($(date +%s%N)/1000000))" >> "${DIRECTORY}"/log.txt
# echo "rpki_setup.sh: "
# time ./setup/rpki_setup.sh "${DIRECTORY}"

# echo ""
# echo ""

echo "configure_ssh.sh: "
echo "configure_ssh.sh $(($(date +%s%N)/1000000))" >> "${DIRECTORY}"/log.txt
time ./setup/configure_ssh.sh "${DIRECTORY}"

echo ""
echo ""

echo "start_snmp.sh: "
echo "start_snmp.sh $(($(date +%s%N)/1000000))" >> "${DIRECTORY}"/log.txt
time ./setup/start_snmp.sh "${DIRECTORY}"

echo ""
echo ""

echo "sFlow setup"
echo "sflow.sh $(($(date +%s%N)/1000000))" >> "${DIRECTORY}"/log.txt
time ./setup/sflow.sh "${DIRECTORY}"

echo ""
echo ""

echo "NetFlow and traffic setup"
echo "netflow.sh $(($(date +%s%N)/1000000))" >> "${DIRECTORY}"/log.txt
time ./setup/netflow.sh "${DIRECTORY}"

echo ""
echo ""

echo "Flowgrind setup"
echo "flowgrind.sh $(($(date +%s%N)/1000000))" >> "${DIRECTORY}"/log.txt
time ./setup/flowgrind.sh "${DIRECTORY}"

echo ""
echo ""

if [[ "$1" == "area" ]]; then
    echo "OSPF area config"
    echo "ospf_area.sh $(($(date +%s%N)/1000000))" >> "${DIRECTORY}"/log.txt
    time ./setup/ospf_area.sh "${DIRECTORY}"

    echo ""
    echo ""
fi

if [[ "$1" == "tunnel" ]]; then
    echo "tunnel config"
    echo "tunnels.sh $(($(date +%s%N)/1000000))" >> "${DIRECTORY}"/log.txt
    time ./setup/tunnels.sh "${DIRECTORY}"

    echo ""
    echo ""
fi

if [[ "$1" == "mpls" ]]; then
    echo "mpls config"
    echo "mpls.sh $(($(date +%s%N)/1000000))" >> "${DIRECTORY}"/log.txt
    time ./setup/mpls.sh "${DIRECTORY}"

    echo ""
    echo ""
fi

if [[ "$1" == "demo" ]]; then
    echo "demo config"
    echo "demo.sh $(($(date +%s%N)/1000000))" >> "${DIRECTORY}"/log.txt
    time ./setup/demo.sh "${DIRECTORY}" "${disable_mpls}"

    echo ""
    echo ""

# echo "Applying hijacks: "
# echo "hijacks $(($(date +%s%N)/1000000))" >> "${DIRECTORY}"/log.txt
# time ./setup/hijack_config.py "${DIRECTORY}"

# echo "$(date +%Y-%m-%d_%H-%M-%S)"

# echo ""
# echo ""

# echo "website_setup.sh: "
# echo "website_setup.sh $(($(date +%s%N)/1000000))" >> "${DIRECTORY}"/log.txt
# time ./setup/website_setup.sh "${DIRECTORY}"

# echo ""
# echo ""

# echo "webserver_links.sh: "
# echo "webserver_links.sh $(($(date +%s%N)/1000000))" >> "${DIRECTORY}"/log.txt
# time ./groups/rpki/webserver_links.sh

# echo ""
# echo ""

# echo "history_setup.sh: "
# echo "history_setup.sh $(($(date +%s%N)/1000000))" >> "${DIRECTORY}"/log.txt
# time ./setup/history_setup.sh "${DIRECTORY}"

# echo ""
# echo ""

# # reload dns server config
# if [ -n "$(docker ps | grep "DNS")" ]; then
#     # docker exec -d DNS service bind9 restart
#     docker kill --signal=HUP DNS
# fi

# echo "Waiting 60sec for BGP messages to propagate..."
# sleep 60

# echo "Refreshing selected advertisements: "
# echo "bgp_clear $(($(date +%s%N)/1000000))" >> "${DIRECTORY}"/log.txt
# time ./setup/bgp_clear.sh "${DIRECTORY}"

echo "$(date +%Y-%m-%d_%H-%M-%S)"
