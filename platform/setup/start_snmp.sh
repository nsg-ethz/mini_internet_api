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
    group_router_config="${group_k[3]}"

    readarray routers < "${DIRECTORY}"/config/$group_router_config
    n_routers=${#routers[@]}

    for ((i=0;i<n_routers;i++)); do
        router_i=(${routers[$i]})
        rname="${router_i[0]}"
        property1="${router_i[1]}"

        # temporary to collect data for debugging
        # docker exec -d "${group_number}"_"${rname}"router tcpdump -eni any -w /home/test.pcap &

        # start snmpd on each router container
        docker exec "${group_number}"_"${rname}"router snmpd

        # start lldpd on each router container
        docker exec "${group_number}"_"${rname}"router lldpd -c -x -M 4

    done
done
