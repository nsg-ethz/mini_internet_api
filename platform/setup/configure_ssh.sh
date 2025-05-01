#!/bin/bash
#
# adds a public key to each router and host for SSH-based access

set -o errexit
set -o pipefail
set -o nounset

DIRECTORY="$1"
source "${DIRECTORY}/config/subnet_config.sh"
source "${DIRECTORY}/setup/_parallel_helper.sh"

# read configs
readarray groups < "${DIRECTORY}/config/AS_config.txt"
readarray extern_links < "${DIRECTORY}/config/aslevel_links.txt"
readarray l2_switches < "${DIRECTORY}/config/l2_switches.txt"
readarray l2_links < "${DIRECTORY}/config/l2_links.txt"
readarray l2_hosts < "${DIRECTORY}/config/l2_hosts.txt"

group_numbers="${#groups[@]}"
n_extern_links="${#extern_links[@]}"
n_l2_switches="${#l2_switches[@]}"
n_l2_links="${#l2_links[@]}"
n_l2_hosts="${#l2_hosts[@]}"

# prepare given key
cp "${DIRECTORY}"/config/lab_network.pub "${DIRECTORY}"/groups/authorized_keys

# create initial configuration for each router
for ((k = 0; k < group_numbers; k++)); do
    (
        group_k=(${groups[$k]})
        group_number="${group_k[0]}"
        group_as="${group_k[1]}"
        group_config="${group_k[2]}"
        group_router_config="${group_k[3]}"
        group_internal_links="${group_k[4]}"

        if [ "${group_as}" != "IXP" ]; then

            readarray routers < "${DIRECTORY}/config/${group_router_config}"
            n_routers="${#routers[@]}"

            for ((i = 0; i < n_routers; i++)); do
                router_i=(${routers[$i]})
                rname="${router_i[0]}"
                property1="${router_i[1]}"
                property2="${router_i[2]}"
                dname=$(echo $property2 | cut -s -d ':' -f 2)

                if [ ${#rname} -gt 10 ]; then
                    echo 'ERROR: Router names must have a length lower or equal than 10'
                    exit 1
                fi

                # copy pub key to router
                docker cp "${DIRECTORY}"/groups/authorized_keys "${group_number}_${rname}router":/root/.ssh/authorized_keys > /dev/null

                # copy pub key to host
                docker cp "${DIRECTORY}"/groups/authorized_keys "${group_number}_${rname}host":/root/.ssh/authorized_keys > /dev/null

            done
        fi
    ) &
    wait_if_n_tasks_are_running
done
wait
