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

                host_ipv6="$(subnet_host_router6 ${group_number} ${i} host)"
                router_ipv6="$(subnet_host_router6 ${group_number} ${i} router)"

                # IPv6 address on main interface on host
                docker exec "${group_number}_${rname}host" ip address add "${host_ipv6}" dev "${rname}"router
                docker exec "${group_number}_${rname}host" ip route add default via "${router_ipv6%/*}"

                # 6in4 tunnels
                router_ip="$(subnet_host_router ${group_number} ${i} router)"
                for ((j = 0; j < n_routers; j++)); do
                    router_j=(${routers[$j]})
                    rname2="${router_j[0]}"
                    if [ "${rname}" != "${rname2}" ]; then
                        router_ip_remote="$(subnet_host_router ${group_number} ${j} router)"
                        router_ip_remote6="$(subnet_host_router6 ${group_number} ${j} router)"
                        docker exec "${group_number}_${rname}router" ip tunnel add t_"${rname}"_"${rname2}" mode sit remote "${router_ip_remote%/*}" local "${router_ip%/*}" ttl 255
                        docker exec "${group_number}_${rname}router" ip link set t_"${rname}"_"${rname2}" up
                        docker exec "${group_number}_${rname}router" ip route add "${router_ip_remote6}" dev t_"${rname}"_"${rname2}"
                    fi
                done

                configdir="${DIRECTORY}/groups/g${group_number}/${rname}/config"
                # Create files and directory
                mkdir -p "${configdir}"
                echo "#!/usr/bin/vtysh -f" > "${configdir}/conf_extra.sh"
                chmod +x "${configdir}/conf_extra.sh"
                location="${configdir}/conf_extra.sh"

                {
                    # IPv6 address on main host interface on router
                    echo "interface host"
                    echo "ip address $(subnet_host_router6 ${group_number} ${i} router)"
                    echo "exit"
                } >> "${location}"

                if [[ "$rname" == "R2" ]]; then
                    docker exec "${group_number}_${rname}router" ip tunnel add gre1 mode gre remote 4.0.8.2 local 4.0.7.1 ttl 255
                    docker exec "${group_number}_${rname}router" ip addr add 10.10.10.1/24 dev gre1
                    docker exec "${group_number}_${rname}router" ip link set gre1 up
                    docker exec "${group_number}_${rname}router" ip route add 4.106.0.1/32 dev gre1
                    docker exec "${group_number}_${rname}router" ip route add 4.106.1.1/32 dev gre1
                    docker exec "${group_number}_${rname}router" ip route add 4.106.2.1/32 dev gre1
                fi

                if [[ "$rname" == "R8" ]]; then
                    docker exec "${group_number}_${rname}router" ip tunnel add gre1 mode gre remote 4.0.7.1 local 4.0.8.2 ttl 255
                    docker exec "${group_number}_${rname}router" ip addr add 10.10.10.2/24 dev gre1
                    docker exec "${group_number}_${rname}router" ip link set gre1 up

                    docker exec "${group_number}_${rname}router" ip tunnel add gre2 mode gre remote 4.0.10.1 local 4.0.9.1 ttl 255
                    docker exec "${group_number}_${rname}router" ip addr add 20.20.20.2/24 dev gre2
                    docker exec "${group_number}_${rname}router" ip link set gre2 up
                fi

                if [[ "$rname" == "R5" ]]; then
                    docker exec "${group_number}_${rname}router" ip tunnel add gre2 mode gre remote 4.0.9.1 local 4.0.10.1 ttl 255
                    docker exec "${group_number}_${rname}router" ip addr add 20.20.20.1/24 dev gre2
                    docker exec "${group_number}_${rname}router" ip link set gre2 up
                    docker exec "${group_number}_${rname}router" ip route add 4.101.3.1/32 dev gre2
                    docker exec "${group_number}_${rname}router" ip route add 4.101.4.1/32 dev gre2
                    docker exec "${group_number}_${rname}router" ip route add 4.101.5.1/32 dev gre2
                fi
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
