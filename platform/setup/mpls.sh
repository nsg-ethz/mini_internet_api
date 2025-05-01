#!/bin/bash
#
# creates an initial configuration for every router
# load configuration into router

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
            readarray intern_links < "${DIRECTORY}/config/${group_internal_links}"
            n_routers="${#routers[@]}"
            n_intern_links="${#intern_links[@]}"

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

                configdir="${DIRECTORY}/groups/g${group_number}/${rname}/config"
                # Create files and directoryu
                mkdir -p "${configdir}"
                echo "#!/usr/bin/vtysh -f" > "${configdir}/conf_extra.sh"
                chmod +x "${configdir}/conf_extra.sh"
                location="${configdir}/conf_extra.sh"

                router_id="$(subnet_router ${group_number} ${i})"

                 if [[ "$rname" == "R1" ]]; then
                    {
                        echo "ip route 5.111.0.0/24 5.0.1.2 label 500"
                        echo "ip route 5.111.1.0/24 5.0.1.2 label 500"
                        echo "ip route 5.111.2.0/24 5.0.1.2 label 500"
                        echo "ip route 5.111.3.0/24 5.0.1.2 label 500"
                        echo "ip route 5.111.4.0/24 5.0.1.2 label 500"
                        echo "ip route 5.111.5.0/24 5.0.1.2 label 500"
                    } >> "${location}"
                fi

                 if [[ "$rname" == "R2" ]]; then
                    {
                        echo "mpls lsp 500 5.0.9.2 501"
                        echo "mpls lsp 504 5.0.16.1 505"
                    } >> "${location}"
                fi

                if [[ "$rname" == "R10" ]]; then
                    {
                        echo "mpls lsp 501 5.0.10.2 502"
                    } >> "${location}"
                fi

                if [[ "$rname" == "R8" ]]; then
                    {
                        echo "mpls lsp 502 5.0.7.1 503"
                    } >> "${location}"
                fi

                if [[ "$rname" == "R3" ]]; then
                    {
                        echo "mpls lsp 503 5.0.2.1 504"
                    } >> "${location}"
                fi

                if [[ "$rname" == "R13" ]]; then
                    {
                        echo "mpls lsp 505 5.0.15.1 506"
                    } >> "${location}"
                fi

                if [[ "$rname" == "R7" ]]; then
                    {
                        echo "mpls lsp 506 5.0.14.1 507"
                    } >> "${location}"
                fi

                if [[ "$rname" == "R12" ]]; then
                    {
                        echo "mpls lsp 507 5.0.13.1 508"
                    } >> "${location}"
                fi

                if [[ "$rname" == "R4" ]]; then
                    {
                        echo "mpls lsp 508 5.0.12.1 implicit-null"
                    } >> "${location}"
                fi

                {
                    echo "mpls ldp"
                    echo "router-id "${router_id%/*}""
                    echo "address-family ipv4"
                    echo "discovery transport-address "${router_id%/*}""
                    echo "exit"
                    echo "exit"
                    echo "no router bgp ${group_number}"
                } >> "${location}"
                    # we disable BGP completely for now
                    # if we would have eBGP sessions, we would need iBGP full mesh between the border routers
                    # but only between these
                    # BGP not needed otherwise as we have MPLS for now

            done

            for ((i = 0; i < n_intern_links; i++)); do
                row_i=(${intern_links[$i]})
                router1="${row_i[0]}"
                router2="${row_i[1]}"
                location1="${DIRECTORY}"/groups/g"${group_number}"/"${router1}"/config/conf_extra.sh
                location2="${DIRECTORY}"/groups/g"${group_number}"/"${router2}"/config/conf_extra.sh
                {
                    echo "interface port_${router2}"
                    echo "no ip ospf bfd"
                    echo "exit"
                    echo "mpls ldp"
                    echo "address-family ipv4"
                    echo "interface port_"${router2}""
                    echo "exit"
                    echo "exit"
                    echo "exit"
                } >> "${location1}"
                {
                    echo "interface port_${router1}"
                    echo "no ip ospf bfd"
                    echo "exit"
                    echo "mpls ldp"
                    echo "address-family ipv4"
                    echo "interface port_"${router1}""
                    echo "exit"
                    echo "exit"
                    echo "exit"
                } >> "${location2}"
            done
        fi
    ) &
    wait_if_n_tasks_are_running
done
wait

echo 'Sleeping 2 seconds...'
sleep 2

for ((k = 0; k < group_numbers; k++)); do
    (
        group_k=(${groups[$k]})
        group_number="${group_k[0]}"
        group_as="${group_k[1]}"
        group_config="${group_k[2]}"
        group_config="${group_k[2]}"
        group_router_config="${group_k[3]}"
        group_internal_links="${group_k[4]}"

        if [ "${group_as}" != "IXP" ]; then

            readarray routers < "${DIRECTORY}/config/${group_router_config}"
            n_routers=${#routers[@]}

            for ((i = 0; i < n_routers; i++)); do
                router_i=(${routers[$i]})
                rname="${router_i[0]}"
                property1="${router_i[1]}"

                config_dir="${DIRECTORY}/groups/g${group_number}/${rname}/config"

                if [ "$group_config" == "Config" ]; then
                    docker cp "${config_dir}/conf_extra.sh" "${group_number}_${rname}router":/home/conf_extra.sh > /dev/null
                    docker exec -d "${group_number}_${rname}router" ./home/conf_extra.sh &
                fi

            done
        fi
    ) &
    wait_if_n_tasks_are_running # no ip command
done
wait
