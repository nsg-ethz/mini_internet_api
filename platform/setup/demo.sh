#!/bin/bash

set -o errexit
set -o pipefail
set -o nounset

DIRECTORY="$1"
disable_mpls="$2"
source "${DIRECTORY}/config/subnet_config.sh"
source "${DIRECTORY}/setup/_parallel_helper.sh"

if [ "$disable_mpls" == true ]; then
    echo "MPLS tunnels are disabled!"
fi


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

for ((k = 0; k < group_numbers; k++)); do
    (
        group_k=(${groups[$k]})
        group_number="${group_k[0]}"
        group_as="${group_k[1]}"
        group_config="${group_k[2]}"
        group_router_config="${group_k[3]}"
        group_internal_links="${group_k[4]}"

        # for now no special config for external ASes
        if [ "$group_number" -eq 55 ]; then

            if [ "$disable_mpls" == false ]; then
                # enabling MPLS on all relevant interfaces
                docker exec -d ${group_number}_bb1-7router sysctl -w net.mpls.conf."port_bb2-1".input=1
                docker exec -d ${group_number}_bb1-7router sysctl -w net.mpls.conf."port_bb2-2".input=1
                docker exec -d ${group_number}_bb1-8router sysctl -w net.mpls.conf."port_bb2-1".input=1
                docker exec -d ${group_number}_bb1-8router sysctl -w net.mpls.conf."port_bb2-3".input=1
                docker exec -d ${group_number}_bb2-1router sysctl -w net.mpls.conf."port_bb1-7".input=1
                docker exec -d ${group_number}_bb2-1router sysctl -w net.mpls.conf."port_bb1-8".input=1
                docker exec -d ${group_number}_bb2-1router sysctl -w net.mpls.conf."port_bb2-2".input=1
                docker exec -d ${group_number}_bb2-1router sysctl -w net.mpls.conf."port_bb2-3".input=1
                docker exec -d ${group_number}_bb2-2router sysctl -w net.mpls.conf."port_bb1-7".input=1
                docker exec -d ${group_number}_bb2-2router sysctl -w net.mpls.conf."port_bb2-1".input=1
                docker exec -d ${group_number}_bb2-2router sysctl -w net.mpls.conf."port_bb2-4".input=1
                docker exec -d ${group_number}_bb2-2router sysctl -w net.mpls.conf."port_bb2-5".input=1
                docker exec -d ${group_number}_bb2-3router sysctl -w net.mpls.conf."port_bb1-8".input=1
                docker exec -d ${group_number}_bb2-3router sysctl -w net.mpls.conf."port_bb2-1".input=1
                docker exec -d ${group_number}_bb2-3router sysctl -w net.mpls.conf."port_bb2-4".input=1
                docker exec -d ${group_number}_bb2-3router sysctl -w net.mpls.conf."port_bb2-5".input=1
                docker exec -d ${group_number}_bb2-4router sysctl -w net.mpls.conf."port_bb2-2".input=1
                docker exec -d ${group_number}_bb2-4router sysctl -w net.mpls.conf."port_bb2-3".input=1
                docker exec -d ${group_number}_bb2-4router sysctl -w net.mpls.conf."port_l2-1".input=1
                docker exec -d ${group_number}_bb2-5router sysctl -w net.mpls.conf."port_bb2-2".input=1
                docker exec -d ${group_number}_bb2-5router sysctl -w net.mpls.conf."port_bb2-3".input=1
                docker exec -d ${group_number}_bb2-5router sysctl -w net.mpls.conf."port_l2-1".input=1
                docker exec -d ${group_number}_l2-1router sysctl -w net.mpls.conf."port_bb2-4".input=1
                docker exec -d ${group_number}_l2-1router sysctl -w net.mpls.conf."port_bb2-5".input=1
            fi

            # central syslog collector setup
            # using l1-2 host as collection point for now
            # in UDP mode to keep overhead lower
            docker exec "${group_number}_l1-2host" mkdir -p /etc/rsyslog.d/
            docker cp "${DIRECTORY}/config/logs/10-collector.conf" "${group_number}_l1-2host":"/etc/rsyslog.d/10-collector.conf" > /dev/null
            docker exec -d "${group_number}_l1-2host" rsyslogd &

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

                # start log export to central collector
                docker exec "${group_number}_${rname}router" mkdir -p /etc/rsyslog.d/
                docker cp "${DIRECTORY}/config/logs/${rname}.conf" "${group_number}_${rname}router":"/etc/rsyslog.d/10-sender.conf" > /dev/null
                docker exec -d "${group_number}_${rname}router" rsyslogd &

                # move dummy host file to container
                docker cp "${DIRECTORY}/config/hosts/${rname}router.json" "${group_number}_${rname}router":"/home/host.json" > /dev/null

                # move dummy iptables file to container
                docker cp "${DIRECTORY}/config/iptables/${rname}router.iptables" "${group_number}_${rname}router":"/home/iptables.iptables" > /dev/null

                configdir="${DIRECTORY}/groups/g${group_number}/${rname}/config"
                # Create files and directoryu
                mkdir -p "${configdir}"
                echo "#!/usr/bin/vtysh -f" > "${configdir}/conf_extra.sh"
                chmod +x "${configdir}/conf_extra.sh"
                location="${configdir}/conf_extra.sh"

                router_id="$(subnet_router ${group_number} ${i})"

                ###################
                # for all routers #
                ###################

                # adding ACL to each router
                # does not work at the moment
                # {
                # } >> "${location}"

                # we disable BGP on all routers, not needed at the moment
                {
                    echo "no router bgp ${group_number}"
                } >> "${location}"

                # enabling iptables rules
                docker exec "${group_number}_${rname}router" /bin/bash -c 'iptables-restore < /home/iptables.iptables'

                ######################
                # individual routers #
                ######################

                if [[ "$rname" == "l1-1" ]]; then
                    # IPv6 setup
                    host_ipv6="$(subnet_host_router6 ${group_number} ${i} host)"
                    router_ipv6="$(subnet_host_router6 ${group_number} ${i} router)"
                    router_ip="$(subnet_host_router ${group_number} ${i} router)"

                    # IPv6 address on main interface on host
                    docker exec "${group_number}_${rname}host" ip address add "${host_ipv6}" dev "${rname}"router
                    docker exec "${group_number}_${rname}host" ip route add default via "${router_ipv6%/*}"

                    # 6in4 tunnel to l1-2
                    router_ip_remote="$(subnet_host_router ${group_number} 1 router)"
                    router_ip_remote6="$(subnet_host_router6 ${group_number} 1 router)"
                    docker exec "${group_number}_${rname}router" ip tunnel add t_"${rname}"_l1-2 mode sit remote "${router_ip_remote%/*}" local "${router_ip%/*}" ttl 255
                    docker exec "${group_number}_${rname}router" ip link set t_"${rname}"_l1-2 up
                    docker exec "${group_number}_${rname}router" ip route add "${router_ip_remote6}" dev t_"${rname}"_l1-2

                    # 6in4 tunnel to dcn1-1
                    router_ip_remote="$(subnet_host_router ${group_number} 2 router)"
                    router_ip_remote6="$(subnet_host_router6 ${group_number} 2 router)"
                    docker exec "${group_number}_${rname}router" ip tunnel add t_"${rname}"_dcn1-1 mode sit remote "${router_ip_remote%/*}" local "${router_ip%/*}" ttl 255
                    docker exec "${group_number}_${rname}router" ip link set t_"${rname}"_dcn1-1 up
                    docker exec "${group_number}_${rname}router" ip route add "${router_ip_remote6}" dev t_"${rname}"_dcn1-1

                    # router IPv6 config
                    {
                        echo "interface host"
                        echo "ip address $(subnet_host_router6 ${group_number} ${i} router)"
                        echo "exit"
                    } >> "${location}"

                    # OSPF area 2
                    {
                        echo "router ospf"
                        echo "no network $(subnet_router_router_intern ${group_number} 0 bridge) area 0"
                        echo "no network $(subnet_router_router_intern ${group_number} 1 bridge) area 0"
                        echo "network $(subnet_router_router_intern ${group_number} 0 bridge) area 2"
                        echo "network $(subnet_router_router_intern ${group_number} 1 bridge) area 2"

                        echo "no network $(subnet_router ${group_number} ${i}) area 0"
                        echo "network $(subnet_router ${group_number} ${i}) area 2"
                        echo "no network $(subnet_host_router ${group_number} ${i} router) area 0"
                        echo "network $(subnet_host_router ${group_number} ${i} router) area 2"

                        for ((j=1;j<6;j++)); do
                            echo "no network $(subnet_host_router_add ${group_number} ${i} router "${j}") area 0"
                            echo "network $(subnet_host_router_add ${group_number} ${i} router "${j}") area 2"
                        done
                        echo "exit"
                    } >> "${location}"
                fi

                if [[ "$rname" == "l1-2" ]]; then
                    # IPv6 setup
                    host_ipv6="$(subnet_host_router6 ${group_number} ${i} host)"
                    router_ipv6="$(subnet_host_router6 ${group_number} ${i} router)"
                    router_ip="$(subnet_host_router ${group_number} ${i} router)"

                    # IPv6 address on main interface on host
                    docker exec "${group_number}_${rname}host" ip address add "${host_ipv6}" dev "${rname}"router
                    docker exec "${group_number}_${rname}host" ip route add default via "${router_ipv6%/*}"

                    # 6in4 tunnel to l1-1
                    router_ip_remote="$(subnet_host_router ${group_number} 0 router)"
                    router_ip_remote6="$(subnet_host_router6 ${group_number} 0 router)"
                    docker exec "${group_number}_${rname}router" ip tunnel add t_"${rname}"_l1-1 mode sit remote "${router_ip_remote%/*}" local "${router_ip%/*}" ttl 255
                    docker exec "${group_number}_${rname}router" ip link set t_"${rname}"_l1-1 up
                    docker exec "${group_number}_${rname}router" ip route add "${router_ip_remote6}" dev t_"${rname}"_l1-1

                    # 6in4 tunnel to dcn1-1
                    router_ip_remote="$(subnet_host_router ${group_number} 2 router)"
                    router_ip_remote6="$(subnet_host_router6 ${group_number} 2 router)"
                    docker exec "${group_number}_${rname}router" ip tunnel add t_"${rname}"_dcn1-1 mode sit remote "${router_ip_remote%/*}" local "${router_ip%/*}" ttl 255
                    docker exec "${group_number}_${rname}router" ip link set t_"${rname}"_dcn1-1 up
                    docker exec "${group_number}_${rname}router" ip route add "${router_ip_remote6}" dev t_"${rname}"_dcn1-1

                    # router IPv6 config
                    {
                        echo "interface host"
                        echo "ip address $(subnet_host_router6 ${group_number} ${i} router)"
                        echo "exit"
                    } >> "${location}"

                    # tunnel which takes traffic towards hosts on l1-1 via l2-1
                    docker exec "${group_number}_${rname}router" ip tunnel add gre1 mode gre remote 55.0.34.2 local 55.0.1.2 ttl 255
                    docker exec "${group_number}_${rname}router" ip addr add 10.10.10.1/24 dev gre1
                    docker exec "${group_number}_${rname}router" ip link set gre1 up
                    docker exec "${group_number}_${rname}router" ip route add 55.101.0.1/32 dev gre1
                    docker exec "${group_number}_${rname}router" ip route add 55.101.1.1/32 dev gre1
                    docker exec "${group_number}_${rname}router" ip route add 55.101.2.1/32 dev gre1
                    docker exec "${group_number}_${rname}router" ip route add 55.101.3.1/32 dev gre1
                    docker exec "${group_number}_${rname}router" ip route add 55.101.4.1/32 dev gre1
                    docker exec "${group_number}_${rname}router" ip route add 55.101.5.1/32 dev gre1

                    # OSPF area 2
                    {
                        echo "router ospf"
                        echo "no network $(subnet_router_router_intern ${group_number} 0 bridge) area 0"
                        echo "no network $(subnet_router_router_intern ${group_number} 2 bridge) area 0"
                        echo "network $(subnet_router_router_intern ${group_number} 0 bridge) area 2"
                        echo "network $(subnet_router_router_intern ${group_number} 2 bridge) area 2"

                        echo "no network $(subnet_router ${group_number} ${i}) area 0"
                        echo "network $(subnet_router ${group_number} ${i}) area 2"
                        echo "no network $(subnet_host_router ${group_number} ${i} router) area 0"
                        echo "network $(subnet_host_router ${group_number} ${i} router) area 2"

                        for ((j=1;j<6;j++)); do
                            echo "no network $(subnet_host_router_add ${group_number} ${i} router "${j}") area 0"
                            echo "network $(subnet_host_router_add ${group_number} ${i} router "${j}") area 2"
                        done
                        echo "exit"
                    } >> "${location}"
                fi

                if [[ "$rname" == "dcn1-1" ]]; then
                    # IPv6 setup
                    host_ipv6="$(subnet_host_router6 ${group_number} ${i} host)"
                    router_ipv6="$(subnet_host_router6 ${group_number} ${i} router)"
                    router_ip="$(subnet_host_router ${group_number} ${i} router)"

                    # IPv6 address on main interface on host
                    docker exec "${group_number}_${rname}host" ip address add "${host_ipv6}" dev "${rname}"router
                    docker exec "${group_number}_${rname}host" ip route add default via "${router_ipv6%/*}"

                    # 6in4 tunnel to l1-2
                    router_ip_remote="$(subnet_host_router ${group_number} 1 router)"
                    router_ip_remote6="$(subnet_host_router6 ${group_number} 1 router)"
                    docker exec "${group_number}_${rname}router" ip tunnel add t_"${rname}"_l1-2 mode sit remote "${router_ip_remote%/*}" local "${router_ip%/*}" ttl 255
                    docker exec "${group_number}_${rname}router" ip link set t_"${rname}"_l1-2 up
                    docker exec "${group_number}_${rname}router" ip route add "${router_ip_remote6}" dev t_"${rname}"_l1-2

                    # 6in4 tunnel to l1-1
                    router_ip_remote="$(subnet_host_router ${group_number} 0 router)"
                    router_ip_remote6="$(subnet_host_router6 ${group_number} 0 router)"
                    docker exec "${group_number}_${rname}router" ip tunnel add t_"${rname}"_l1-1 mode sit remote "${router_ip_remote%/*}" local "${router_ip%/*}" ttl 255
                    docker exec "${group_number}_${rname}router" ip link set t_"${rname}"_l1-1 up
                    docker exec "${group_number}_${rname}router" ip route add "${router_ip_remote6}" dev t_"${rname}"_l1-1

                    # router IPv6 config
                    {
                        echo "interface host"
                        echo "ip address $(subnet_host_router6 ${group_number} ${i} router)"
                        echo "exit"
                    } >> "${location}"

                    # OSPF area 1
                    {
                        echo "router ospf"
                        echo "no network $(subnet_router_router_intern ${group_number} 7 bridge) area 0"
                        echo "no network $(subnet_router_router_intern ${group_number} 10 bridge) area 0"
                        echo "network $(subnet_router_router_intern ${group_number} 7 bridge) area 1"
                        echo "network $(subnet_router_router_intern ${group_number} 10 bridge) area 1"

                        echo "no network $(subnet_router ${group_number} ${i}) area 0"
                        echo "network $(subnet_router ${group_number} ${i}) area 1"
                        echo "no network $(subnet_host_router ${group_number} ${i} router) area 0"
                        echo "network $(subnet_host_router ${group_number} ${i} router) area 1"

                        for ((j=1;j<6;j++)); do
                            echo "no network $(subnet_host_router_add ${group_number} ${i} router "${j}") area 0"
                            echo "network $(subnet_host_router_add ${group_number} ${i} router "${j}") area 1"
                        done
                        echo "exit"
                    } >> "${location}"
                fi

                if [[ "$rname" == "ext1-1" ]]; then
                    # OSPF area 5
                    {
                        echo "router ospf"
                        echo "no network $(subnet_router_router_intern ${group_number} 18 bridge) area 0"
                        echo "no network $(subnet_router_router_intern ${group_number} 23 bridge) area 0"
                        echo "no network $(subnet_router_router_intern ${group_number} 35 bridge) area 0"
                        echo "network $(subnet_router_router_intern ${group_number} 18 bridge) area 5"
                        echo "network $(subnet_router_router_intern ${group_number} 23 bridge) area 5"
                        echo "network $(subnet_router_router_intern ${group_number} 35 bridge) area 5"

                        echo "no network $(subnet_router ${group_number} ${i}) area 0"
                        echo "network $(subnet_router ${group_number} ${i}) area 5"
                        echo "no network $(subnet_host_router ${group_number} ${i} router) area 0"
                        echo "network $(subnet_host_router ${group_number} ${i} router) area 5"

                        for ((j=1;j<6;j++)); do
                            echo "no network $(subnet_host_router_add ${group_number} ${i} router "${j}") area 0"
                            echo "network $(subnet_host_router_add ${group_number} ${i} router "${j}") area 5"
                        done
                        echo "exit"
                    } >> "${location}"

                    # announcing static route via OSPF for all IPs towards external AS
                    {
                        echo "ip route 0.0.0.0/1 179.1.2.163"
                        echo "ip route 128.0.0.0/1 179.1.2.163"
                        echo "ip prefix-list EXT_PREFIX seq 10 permit 0.0.0.0/1"
                        echo "ip prefix-list EXT_PREFIX seq 11 permit 128.0.0.0/1"
                        echo "route-map EXT permit 10"
                        echo "match ip address prefix-list EXT_PREFIX"
                        echo "exit"
                        echo "router ospf"
                        echo "redistribute static route-map EXT"
                        echo "exit"
                    } >> "${location}"
                fi

                if [[ "$rname" == "ext1-2" ]]; then
                    # OSPF area 5
                    {
                        echo "router ospf"
                        echo "no network $(subnet_router_router_intern ${group_number} 35 bridge) area 0"
                        echo "no network $(subnet_router_router_intern ${group_number} 20 bridge) area 0"
                        echo "network $(subnet_router_router_intern ${group_number} 35 bridge) area 5"
                        echo "network $(subnet_router_router_intern ${group_number} 20 bridge) area 5"

                        echo "no network $(subnet_router ${group_number} ${i}) area 0"
                        echo "network $(subnet_router ${group_number} ${i}) area 5"
                        echo "no network $(subnet_host_router ${group_number} ${i} router) area 0"
                        echo "network $(subnet_host_router ${group_number} ${i} router) area 5"

                        for ((j=1;j<6;j++)); do
                            echo "no network $(subnet_host_router_add ${group_number} ${i} router "${j}") area 0"
                            echo "network $(subnet_host_router_add ${group_number} ${i} router "${j}") area 5"
                        done
                        echo "exit"
                    } >> "${location}"
                fi

                if [[ "$rname" == "ext1-3" ]]; then
                    # OSPF area 5
                    {
                        echo "router ospf"
                        echo "no network $(subnet_router_router_intern ${group_number} 19 bridge) area 0"
                        echo "no network $(subnet_router_router_intern ${group_number} 24 bridge) area 0"
                        echo "no network $(subnet_router_router_intern ${group_number} 20 bridge) area 0"
                        echo "network $(subnet_router_router_intern ${group_number} 19 bridge) area 5"
                        echo "network $(subnet_router_router_intern ${group_number} 24 bridge) area 5"
                        echo "network $(subnet_router_router_intern ${group_number} 20 bridge) area 5"

                        echo "no network $(subnet_router ${group_number} ${i}) area 0"
                        echo "network $(subnet_router ${group_number} ${i}) area 5"
                        echo "no network $(subnet_host_router ${group_number} ${i} router) area 0"
                        echo "network $(subnet_host_router ${group_number} ${i} router) area 5"

                        for ((j=1;j<6;j++)); do
                            echo "no network $(subnet_host_router_add ${group_number} ${i} router "${j}") area 0"
                            echo "network $(subnet_host_router_add ${group_number} ${i} router "${j}") area 5"
                        done
                        echo "exit"
                    } >> "${location}"

                    # announcing static route via OSPF for all IPs towards external AS
                    {
                        echo "ip route 0.0.0.0/1 179.1.3.15"
                        echo "ip route 128.0.0.0/1 179.1.3.15"
                        echo "ip prefix-list EXT_PREFIX seq 10 permit 0.0.0.0/1"
                        echo "ip prefix-list EXT_PREFIX seq 11 permit 128.0.0.0/1"
                        echo "route-map EXT permit 10"
                        echo "match ip address prefix-list EXT_PREFIX"
                        echo "exit"
                        echo "router ospf"
                        echo "redistribute static route-map EXT"
                        echo "exit"
                    } >> "${location}"
                fi

                if [[ "$rname" == "l2-1" ]]; then
                    # OSPF area 3
                    {
                        echo "router ospf"
                        echo "no network $(subnet_router_router_intern ${group_number} 33 bridge) area 0"
                        echo "no network $(subnet_router_router_intern ${group_number} 34 bridge) area 0"
                        echo "network $(subnet_router_router_intern ${group_number} 33 bridge) area 3"
                        echo "network $(subnet_router_router_intern ${group_number} 34 bridge) area 3"
                        # echo "network $(subnet_router_router_intern ${group_number} 33 bridge) area 4"
                        # echo "network $(subnet_router_router_intern ${group_number} 34 bridge) area 4"

                        echo "no network $(subnet_router ${group_number} ${i}) area 0"
                        echo "network $(subnet_router ${group_number} ${i}) area 3"
                        # echo "network $(subnet_router ${group_number} ${i}) area 4"
                        echo "no network $(subnet_host_router ${group_number} ${i} router) area 0"
                        echo "network $(subnet_host_router ${group_number} ${i} router) area 3"
                        # echo "network $(subnet_host_router ${group_number} ${i} router) area 4"

                        for ((j=1;j<6;j++)); do
                            echo "no network $(subnet_host_router_add ${group_number} ${i} router "${j}") area 0"
                            echo "network $(subnet_host_router_add ${group_number} ${i} router "${j}") area 3"
                            # echo "network $(subnet_host_router_add ${group_number} ${i} router "${j}") area 4"
                        done
                        echo "exit"
                    } >> "${location}"

                    # dummy tunnel back to l1-2, not sure if that is needed, no routes attached
                    docker exec "${group_number}_${rname}router" ip tunnel add gre1 mode gre remote 55.0.1.2 local 55.0.34.2 ttl 255
                    docker exec "${group_number}_${rname}router" ip addr add 10.10.10.2/24 dev gre1
                    docker exec "${group_number}_${rname}router" ip link set gre1 up

                    if [ "$disable_mpls" == false ]; then
                        # enable MPLS
                        {
                            echo "mpls ldp"
                            echo "router-id "${router_id%/*}""
                            echo "address-family ipv4"
                            echo "discovery transport-address "${router_id%/*}""
                            echo "interface port_bb2-4"
                            echo "interface port_bb2-5"
                            echo "exit"
                            echo "exit"
                            echo "exit"
                        } >> "${location}"
                    fi
                fi

                if [[ "$rname" == "bb1-1" ]]; then
                    # partial OSPF area 2
                    {
                        echo "router ospf"
                        echo "no network $(subnet_router_router_intern ${group_number} 1 bridge) area 0"
                        echo "no network $(subnet_router_router_intern ${group_number} 2 bridge) area 0"
                        echo "network $(subnet_router_router_intern ${group_number} 1 bridge) area 2"
                        echo "network $(subnet_router_router_intern ${group_number} 2 bridge) area 2"

                        echo "exit"
                    } >> "${location}"
                fi

                if [[ "$rname" == "bb1-2" ]]; then
                    # partial OSPF area 1
                    {
                        echo "router ospf"
                        echo "no network $(subnet_router_router_intern ${group_number} 7 bridge) area 0"
                        echo "network $(subnet_router_router_intern ${group_number} 7 bridge) area 1"

                        echo "exit"
                    } >> "${location}"
                fi

                if [[ "$rname" == "bb1-3" ]]; then
                    # partial OSPF area 1
                    {
                        echo "router ospf"
                        echo "no network $(subnet_router_router_intern ${group_number} 10 bridge) area 0"
                        echo "network $(subnet_router_router_intern ${group_number} 10 bridge) area 1"

                        echo "exit"
                    } >> "${location}"
                fi

                if [[ "$rname" == "bb1-4" ]]; then
                    continue
                fi

                if [[ "$rname" == "bb1-5" ]]; then
                    # kill LLDP fully on this router
                    docker exec "${group_number}"_"${rname}"router pkill lldpd
                fi

                if [[ "$rname" == "bb1-6" ]]; then
                    # partial OSPF area 5
                    {
                        echo "router ospf"
                        echo "no network $(subnet_router_router_intern ${group_number} 18 bridge) area 0"
                        echo "no network $(subnet_router_router_intern ${group_number} 19 bridge) area 0"
                        echo "network $(subnet_router_router_intern ${group_number} 18 bridge) area 5"
                        echo "network $(subnet_router_router_intern ${group_number} 19 bridge) area 5"

                        echo "exit"
                    } >> "${location}"

                    # loss on link towards bb1-7 (unidirectional)
                    docker exec "${group_number}"_"${rname}"router tc qdisc del dev port_bb1-7 root
                    docker exec "${group_number}"_"${rname}"router tc qdisc add dev port_bb1-7 root handle 1:0 netem delay 5ms loss 1%

                fi

                if [[ "$rname" == "bb1-7" ]]; then
                    # partial OSPF area 3
                    {
                        echo "router ospf"
                        echo "no network $(subnet_router_router_intern ${group_number} 21 bridge) area 0"
                        echo "no network $(subnet_router_router_intern ${group_number} 22 bridge) area 0"
                        echo "network $(subnet_router_router_intern ${group_number} 21 bridge) area 3"
                        echo "network $(subnet_router_router_intern ${group_number} 22 bridge) area 3"

                        echo "exit"
                    } >> "${location}"

                    if [ "$disable_mpls" == false ]; then
                        # enable MPLS
                        {
                            echo "mpls ldp"
                            echo "router-id "${router_id%/*}""
                            echo "address-family ipv4"
                            echo "discovery transport-address "${router_id%/*}""
                            echo "interface port_bb2-1"
                            echo "interface port_bb2-2"
                            echo "exit"
                            echo "exit"
                            echo "exit"
                        } >> "${location}"
                    fi
                fi

                if [[ "$rname" == "bb1-8" ]]; then
                    # partial OSPF area 3 & 5
                    {
                        echo "router ospf"
                        echo "no network $(subnet_router_router_intern ${group_number} 25 bridge) area 0"
                        echo "no network $(subnet_router_router_intern ${group_number} 26 bridge) area 0"
                        echo "network $(subnet_router_router_intern ${group_number} 25 bridge) area 3"
                        echo "network $(subnet_router_router_intern ${group_number} 26 bridge) area 3"

                        echo "no network $(subnet_router_router_intern ${group_number} 23 bridge) area 0"
                        echo "no network $(subnet_router_router_intern ${group_number} 24 bridge) area 0"
                        echo "network $(subnet_router_router_intern ${group_number} 23 bridge) area 5"
                        echo "network $(subnet_router_router_intern ${group_number} 24 bridge) area 5"

                        echo "exit"
                    } >> "${location}"

                    if [ "$disable_mpls" == false ]; then
                        # enable MPLS
                        {
                            echo "mpls ldp"
                            echo "router-id "${router_id%/*}""
                            echo "address-family ipv4"
                            echo "discovery transport-address "${router_id%/*}""
                            echo "interface port_bb2-1"
                            echo "interface port_bb2-3"  ## TEMP_DISABLE_MPLS
                            echo "exit"
                            echo "exit"
                            echo "exit"
                        } >> "${location}"
                    fi
                fi

                if [[ "$rname" == "bb2-1" ]]; then
                    # OSPF area 3
                    {
                        echo "router ospf"
                        echo "no network $(subnet_router_router_intern ${group_number} 21 bridge) area 0"
                        echo "no network $(subnet_router_router_intern ${group_number} 25 bridge) area 0"
                        echo "no network $(subnet_router_router_intern ${group_number} 27 bridge) area 0"
                        echo "no network $(subnet_router_router_intern ${group_number} 28 bridge) area 0"
                        echo "network $(subnet_router_router_intern ${group_number} 21 bridge) area 3"
                        echo "network $(subnet_router_router_intern ${group_number} 25 bridge) area 3"
                        echo "network $(subnet_router_router_intern ${group_number} 27 bridge) area 3"
                        echo "network $(subnet_router_router_intern ${group_number} 28 bridge) area 3"

                        echo "no network $(subnet_router ${group_number} ${i}) area 0"
                        echo "network $(subnet_router ${group_number} ${i}) area 3"
                        echo "no network $(subnet_host_router ${group_number} ${i} router) area 0"
                        echo "network $(subnet_host_router ${group_number} ${i} router) area 3"

                        for ((j=1;j<6;j++)); do
                            echo "no network $(subnet_host_router_add ${group_number} ${i} router "${j}") area 0"
                            echo "network $(subnet_host_router_add ${group_number} ${i} router "${j}") area 3"
                        done
                        echo "exit"
                    } >> "${location}"

                    if [ "$disable_mpls" == false ]; then
                        # enable MPLS
                        {
                            echo "mpls ldp"
                            echo "router-id "${router_id%/*}""
                            echo "address-family ipv4"
                            echo "discovery transport-address "${router_id%/*}""
                            echo "interface port_bb1-7"
                            echo "interface port_bb1-8"
                            echo "interface port_bb2-2"
                            echo "interface port_bb2-3"
                            echo "exit"
                            echo "exit"
                            echo "exit"
                        } >> "${location}"
                    fi
                fi

                if [[ "$rname" == "bb2-2" ]]; then
                    # OSPF area 3
                    {
                        echo "router ospf"
                        echo "no network $(subnet_router_router_intern ${group_number} 22 bridge) area 0"
                        echo "no network $(subnet_router_router_intern ${group_number} 27 bridge) area 0"
                        echo "no network $(subnet_router_router_intern ${group_number} 29 bridge) area 0"
                        echo "no network $(subnet_router_router_intern ${group_number} 30 bridge) area 0"
                        echo "network $(subnet_router_router_intern ${group_number} 22 bridge) area 3"
                        echo "network $(subnet_router_router_intern ${group_number} 27 bridge) area 3"
                        echo "network $(subnet_router_router_intern ${group_number} 29 bridge) area 3"
                        echo "network $(subnet_router_router_intern ${group_number} 30 bridge) area 3"

                        echo "no network $(subnet_router ${group_number} ${i}) area 0"
                        echo "network $(subnet_router ${group_number} ${i}) area 3"
                        echo "no network $(subnet_host_router ${group_number} ${i} router) area 0"
                        echo "network $(subnet_host_router ${group_number} ${i} router) area 3"

                        for ((j=1;j<6;j++)); do
                            echo "no network $(subnet_host_router_add ${group_number} ${i} router "${j}") area 0"
                            echo "network $(subnet_host_router_add ${group_number} ${i} router "${j}") area 3"
                        done
                        echo "exit"
                    } >> "${location}"

                    # disable LLDP on port_bb2-4 & port_bb2-5
                    docker exec "${group_number}"_"${rname}"router pkill lldpd
                    docker exec "${group_number}"_"${rname}"router lldpd -c -x -M 4 -I port_bb1-7,port_bb2-1

                    if [ "$disable_mpls" == false ]; then
                        # enable MPLS
                        {
                            echo "mpls ldp"
                            echo "router-id "${router_id%/*}""
                            echo "address-family ipv4"
                            echo "discovery transport-address "${router_id%/*}""
                            echo "interface port_bb1-7"
                            echo "interface port_bb2-1"
                            echo "interface port_bb2-4"
                            echo "interface port_bb2-5"
                            echo "exit"
                            echo "exit"
                            echo "exit"
                        } >> "${location}"
                    fi
                fi

                if [[ "$rname" == "bb2-3" ]]; then
                    # OSPF area 3
                    {
                        echo "router ospf"
                        echo "no network $(subnet_router_router_intern ${group_number} 26 bridge) area 0"
                        echo "no network $(subnet_router_router_intern ${group_number} 28 bridge) area 0"
                        echo "no network $(subnet_router_router_intern ${group_number} 31 bridge) area 0"
                        echo "no network $(subnet_router_router_intern ${group_number} 32 bridge) area 0"
                        echo "network $(subnet_router_router_intern ${group_number} 26 bridge) area 3"
                        echo "network $(subnet_router_router_intern ${group_number} 28 bridge) area 3"
                        echo "network $(subnet_router_router_intern ${group_number} 31 bridge) area 3"
                        echo "network $(subnet_router_router_intern ${group_number} 32 bridge) area 3"

                        echo "no network $(subnet_router ${group_number} ${i}) area 0"
                        echo "network $(subnet_router ${group_number} ${i}) area 3"
                        echo "no network $(subnet_host_router ${group_number} ${i} router) area 0"
                        echo "network $(subnet_host_router ${group_number} ${i} router) area 3"

                        for ((j=1;j<6;j++)); do
                            echo "no network $(subnet_host_router_add ${group_number} ${i} router "${j}") area 0"
                            echo "network $(subnet_host_router_add ${group_number} ${i} router "${j}") area 3"
                        done
                        echo "exit"
                    } >> "${location}"

                    # loss on link towards bb2-5 (bidirectional)
                    docker exec "${group_number}"_"${rname}"router tc qdisc del dev port_bb2-5 root
                    docker exec "${group_number}"_"${rname}"router tc qdisc add dev port_bb2-5 root handle 1:0 netem delay 5ms loss 1%

                    if [ "$disable_mpls" == false ]; then
                        # enable MPLS
                        {
                            echo "mpls ldp"
                            echo "router-id "${router_id%/*}""
                            echo "address-family ipv4"
                            echo "discovery transport-address "${router_id%/*}""
                            echo "interface port_bb1-8"
                            echo "interface port_bb2-1"
                            echo "interface port_bb2-4"  ## TEMP_DISABLE_MPLS
                            echo "interface port_bb2-5"
                            echo "exit"
                            echo "exit"
                            echo "exit"
                        } >> "${location}"
                    fi
                fi

                if [[ "$rname" == "bb2-4" ]]; then
                    # OSPF area 3
                    {
                        echo "router ospf"
                        echo "no network $(subnet_router_router_intern ${group_number} 29 bridge) area 0"
                        echo "no network $(subnet_router_router_intern ${group_number} 31 bridge) area 0"
                        echo "no network $(subnet_router_router_intern ${group_number} 33 bridge) area 0"
                        echo "network $(subnet_router_router_intern ${group_number} 29 bridge) area 3"
                        echo "network $(subnet_router_router_intern ${group_number} 31 bridge) area 3"
                        echo "network $(subnet_router_router_intern ${group_number} 33 bridge) area 3"
                        # echo "network $(subnet_router_router_intern ${group_number} 33 bridge) area 4"

                        echo "no network $(subnet_router ${group_number} ${i}) area 0"
                        echo "network $(subnet_router ${group_number} ${i}) area 3"
                        echo "no network $(subnet_host_router ${group_number} ${i} router) area 0"
                        echo "network $(subnet_host_router ${group_number} ${i} router) area 3"

                        for ((j=1;j<6;j++)); do
                            echo "no network $(subnet_host_router_add ${group_number} ${i} router "${j}") area 0"
                            echo "network $(subnet_host_router_add ${group_number} ${i} router "${j}") area 3"
                        done
                        echo "exit"
                    } >> "${location}"

                    if [ "$disable_mpls" == false ]; then
                        # enable MPLS
                        {
                            echo "mpls ldp"
                            echo "router-id "${router_id%/*}""
                            echo "address-family ipv4"
                            echo "discovery transport-address "${router_id%/*}""
                            echo "interface port_bb2-2"
                            echo "interface port_bb2-3"
                            echo "interface port_l2-1"
                            echo "exit"
                            echo "exit"
                            echo "exit"
                        } >> "${location}"
                    fi
                fi

                if [[ "$rname" == "bb2-5" ]]; then
                    # OSPF area 3
                    {
                        echo "router ospf"
                        echo "no network $(subnet_router_router_intern ${group_number} 30 bridge) area 0"
                        echo "no network $(subnet_router_router_intern ${group_number} 32 bridge) area 0"
                        echo "no network $(subnet_router_router_intern ${group_number} 34 bridge) area 0"
                        echo "network $(subnet_router_router_intern ${group_number} 30 bridge) area 3"
                        echo "network $(subnet_router_router_intern ${group_number} 32 bridge) area 3"
                        echo "network $(subnet_router_router_intern ${group_number} 34 bridge) area 3"
                        # echo "network $(subnet_router_router_intern ${group_number} 34 bridge) area 4"

                        echo "no network $(subnet_router ${group_number} ${i}) area 0"
                        echo "network $(subnet_router ${group_number} ${i}) area 3"
                        echo "no network $(subnet_host_router ${group_number} ${i} router) area 0"
                        echo "network $(subnet_host_router ${group_number} ${i} router) area 3"

                        for ((j=1;j<6;j++)); do
                            echo "no network $(subnet_host_router_add ${group_number} ${i} router "${j}") area 0"
                            echo "network $(subnet_host_router_add ${group_number} ${i} router "${j}") area 3"
                        done
                        echo "exit"
                    } >> "${location}"

                    # disable LLDP on port_bb2-2 (to have it disable from both ends)
                    docker exec "${group_number}"_"${rname}"router pkill lldpd
                    docker exec "${group_number}"_"${rname}"router lldpd -c -x -M 4 -I port_bb2-3,port_l2-1

                    # loss on link towards bb2-3 (bidirectional)
                    docker exec "${group_number}"_"${rname}"router tc qdisc del dev port_bb2-3 root
                    docker exec "${group_number}"_"${rname}"router tc qdisc add dev port_bb2-3 root handle 1:0 netem delay 5ms loss 1%

                    if [ "$disable_mpls" == false ]; then
                        # enable MPLS
                        {
                            echo "mpls ldp"
                            echo "router-id "${router_id%/*}""
                            echo "address-family ipv4"
                            echo "discovery transport-address "${router_id%/*}""
                            echo "interface port_bb2-2"
                            echo "interface port_bb2-3"
                            echo "interface port_l2-1"
                            echo "exit"
                            echo "exit"
                            echo "exit"
                        } >> "${location}"
                    fi
                fi

                # write config out
                {
                    echo "exit"
                    echo "write memory"
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

        if [ "$group_number" -eq 55 ]; then

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
