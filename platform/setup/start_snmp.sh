#!/bin/bash
#
# start SNMP collection

set -o errexit
set -o pipefail
set -o nounset

DIRECTORY="$1"
DOCKERHUB_USER="${2:-thomahol}"
source "${DIRECTORY}"/config/subnet_config.sh
source "${DIRECTORY}"/setup/_parallel_helper.sh

# read configs
readarray groups < "${DIRECTORY}"/config/AS_config.txt
readarray extern_links < "${DIRECTORY}"/config/aslevel_links.txt

group_numbers=${#groups[@]}

# Check if there is a SNMP collector in each AS
for ((k=0;k<group_numbers;k++)); do
    group_k=(${groups[$k]})
    group_number="${group_k[0]}"
    group_as="${group_k[1]}"
    group_config="${group_k[2]}"
    group_router_config="${group_k[3]}"
    group_internal_links="${group_k[4]}"
    group_layer2_switches="${group_k[5]}"
    group_layer2_hosts="${group_k[6]}"
    group_layer2_links="${group_k[7]}"

    readarray routers < "${DIRECTORY}"/config/$group_router_config
    readarray l2_switches < "${DIRECTORY}"/config/$group_layer2_switches
    readarray l2_hosts < "${DIRECTORY}"/config/$group_layer2_hosts
    readarray l2_links < "${DIRECTORY}"/config/$group_layer2_links

    n_routers=${#routers[@]}
    n_l2_switches=${#l2_switches[@]}
    n_l2_hosts=${#l2_hosts[@]}
    n_l2_links=${#l2_links[@]}

    for ((i=0;i<n_routers;i++)); do
        router_i=(${routers[$i]})
        rname="${router_i[0]}"
        property1="${router_i[1]}"

        # temporary to collect data for debugging
        # docker exec -d "${group_number}"_"${rname}"router tcpdump -eni any -w /home/test.pcap &

        # start snmpd on each router container
        docker exec "${group_number}"_"${rname}"router snmpd

        # sleep a bit to give SNMP agent time to start before LLDP tries to use SNMP
        sleep 2

        # start lldpd on each router container
        # docker exec "${group_number}"_"${rname}"router pkill lldpd
        # sleep 1
        docker exec "${group_number}"_"${rname}"router lldpd -c -x -M 4

    done

    # SNMP for all L2 hosts
    for ((l = 0; l < n_l2_hosts; l++)); do
        host_l=(${l2_hosts[$l]})
        hname="${host_l[0]}"
        l2name="${host_l[2]}"
        sname="${host_l[3]}"

        docker exec -d "${group_number}""_L2_""${l2name}_${sname}" snmpd
    done

    # SNMP for all L2 swithces
    for ((l = 0; l < n_l2_switches; l++)); do
        switch_l=(${l2_switches[$l]})
        l2name="${switch_l[0]}"
        sname="${switch_l[1]}"

        docker exec -d "${group_number}""_L2_""${l2name}_${sname}" snmpd
    done
done
