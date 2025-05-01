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

            # we only do it once if all-in-one setup
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

                {

                    # R1, R2, and R5 are already correct
                    if [[ "$i" -eq "2" ]]; then
                        echo "no router ospf"
                        echo "router ospf"
                        echo "network $(subnet_router_router_intern ${group_number} 1 2) area 0"
                        echo "network $(subnet_router_router_intern ${group_number} 3 1) area 0"
                        echo "network $(subnet_router_router_intern ${group_number} 4 1) area 0"
                        echo "network $(subnet_router_router_intern ${group_number} 5 1) area 1"
                        echo "network $(subnet_router_router_intern ${group_number} 6 1) area 1"
                        echo "network $(subnet_router_router_intern ${group_number} 12 1) area 2"

                        echo "network $(subnet_router_router_intern ${group_number} ${i} 1) area 0"

                        echo "network $(subnet_host_router ${group_number} ${i} router) area 0"

                        echo "network $(subnet_router ${group_number} ${i}) area 0"

                        for ((j=1;j<6;j++)); do
                            echo "network $(subnet_host_router_add ${group_number} ${i} router "${j}") area 0"
                        done

                        # special summarization rules
                        echo "area 0 range 3.101.0.0/16"
                        echo "area 0 range 3.102.0.0/16"
                        echo "area 0 range 3.103.0.0/16"
                        echo "area 0 range 3.104.0.0/16"
                        echo "area 0 range 3.105.0.0/16"
                        echo "area 1 range 3.106.0.0/16"
                        echo "area 1 range 3.107.0.0/16"
                        echo "area 1 range 3.109.0.0/16"
                        echo "area 2 range 3.110.0.0/16"
                        echo "area 2 range 3.108.0.0/16 cost 0"
                    fi

                    if [[ "$i" -eq "3" ]]; then
                        echo "no router ospf"
                        echo "router ospf"
                        echo "network $(subnet_router_router_intern ${group_number} 2 2) area 0"
                        echo "network $(subnet_router_router_intern ${group_number} 3 2) area 0"
                        echo "network $(subnet_router_router_intern ${group_number} 7 1) area 0"
                        echo "network $(subnet_router_router_intern ${group_number} 8 1) area 2"

                        echo "network $(subnet_host_router ${group_number} ${i} router) area 0"

                        echo "network $(subnet_router ${group_number} ${i}) area 0"

                        for ((j=1;j<6;j++)); do
                            echo "network $(subnet_host_router_add ${group_number} ${i} router "${j}") area 0"
                        done

                        # special summarization rules
                        echo "area 0 range 3.101.0.0/16"
                        echo "area 0 range 3.102.0.0/16"
                        echo "area 0 range 3.103.0.0/16"
                        echo "area 0 range 3.104.0.0/16"
                        echo "area 0 range 3.105.0.0/16"
                        echo "area 2 range 3.110.0.0/16"
                        echo "area 2 range 3.108.0.0/16 not-advertise"
                    fi

                    if [[ "$i" -eq "5" ]]; then
                        echo "no router ospf"
                        echo "router ospf"
                        echo "network $(subnet_router_router_intern ${group_number} 5 2) area 1"
                        echo "network $(subnet_router_router_intern ${group_number} 9 1) area 1"
                        echo "network $(subnet_host_router ${group_number} 2 router) area 1"
                        echo "network $(subnet_host_router ${group_number} 8 router) area 1"

                        echo "network $(subnet_host_router ${group_number} ${i} router) area 1"

                        echo "network $(subnet_router ${group_number} ${i}) area 1"

                        for ((j=1;j<6;j++)); do
                            echo "network $(subnet_host_router_add ${group_number} ${i} router "${j}") area 1"
                        done
                    fi

                    if [[ "$i" -eq "6" ]]; then
                        echo "no router ospf"
                        echo "router ospf"
                        echo "network $(subnet_router_router_intern ${group_number} 6 2) area 1"
                        echo "network $(subnet_router_router_intern ${group_number} 10 1) area 1"

                        echo "network $(subnet_host_router ${group_number} ${i} router) area 1"

                        echo "network $(subnet_router ${group_number} ${i}) area 1"

                        for ((j=1;j<6;j++)); do
                            echo "network $(subnet_host_router_add ${group_number} ${i} router "${j}") area 1"
                        done
                    fi

                    if [[ "$i" -eq "7" ]]; then
                        echo "no router ospf"
                        echo "router ospf"
                        echo "network $(subnet_router_router_intern ${group_number} 8 2) area 2"
                        echo "network $(subnet_router_router_intern ${group_number} 11 1) area 2"

                        echo "network $(subnet_host_router ${group_number} ${i} router) area 2"

                        echo "network $(subnet_router ${group_number} ${i}) area 2"

                        for ((j=1;j<6;j++)); do
                            echo "network $(subnet_host_router_add ${group_number} ${i} router "${j}") area 2"
                        done
                    fi

                    if [[ "$i" -eq "8" ]]; then
                        echo "no router ospf"
                        echo "router ospf"
                        echo "network $(subnet_router_router_intern ${group_number} 9 2) area 1"
                        echo "network $(subnet_router_router_intern ${group_number} 10 2) area 1"

                        echo "network $(subnet_host_router ${group_number} ${i} router) area 1"

                        echo "network $(subnet_router ${group_number} ${i}) area 1"

                        for ((j=1;j<6;j++)); do
                            echo "network $(subnet_host_router_add ${group_number} ${i} router "${j}") area 1"
                        done
                    fi

                    if [[ "$i" -eq "9" ]]; then
                        echo "no router ospf"
                        echo "router ospf"
                        echo "network $(subnet_router_router_intern ${group_number} 11 2) area 2"
                        echo "network $(subnet_router_router_intern ${group_number} 12 2) area 2"

                        echo "network $(subnet_host_router ${group_number} ${i} router) area 2"

                        echo "network $(subnet_router ${group_number} ${i}) area 2"

                        for ((j=1;j<6;j++)); do
                            echo "network $(subnet_host_router_add ${group_number} ${i} router "${j}") area 2"
                        done
                    fi
                } >> "${location}"
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
