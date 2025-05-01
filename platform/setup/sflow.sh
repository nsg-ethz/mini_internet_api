#!/bin/bash

DIRECTORY="$1"
source "${DIRECTORY}"/config/subnet_config.sh

# read configs
readarray groups < "${DIRECTORY}"/config/AS_config.txt
group_numbers=${#groups[@]}

#create all container
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

    if [ "${group_as}" != "IXP" ];then

        readarray routers < "${DIRECTORY}"/config/$group_router_config
        readarray intern_links < "${DIRECTORY}/config/${group_internal_links}"
        n_routers=${#routers[@]}
        n_intern_links="${#intern_links[@]}"

        for ((i = 0; i < n_intern_links; i++)); do
            row_i=(${intern_links[$i]})
            router1="${row_i[0]}"
            router2="${row_i[1]}"

            docker exec "$group_number"_"$router1"router tc qdisc add dev port_${router2} handle ffff: ingress
            docker exec "$group_number"_"$router1"router tc filter add dev port_${router2} parent ffff: matchall action sample rate 10 group 1
            docker exec "$group_number"_"$router2"router tc qdisc add dev port_${router1} handle ffff: ingress
            docker exec "$group_number"_"$router2"router tc filter add dev port_${router1} parent ffff: matchall action sample rate 10 group 1

        done

        for ((i=0;i<n_routers;i++)); do
            router_i=(${routers[$i]})
            rname="${router_i[0]}"
            property1="${router_i[1]}"
            property2="${router_i[2]}"
            htype=$(echo $property2 | cut -d ':' -f 1)
            dname=$(echo $property2 | cut -d ':' -f 2)

            main_ip="$(subnet_netflow_collector "${group_number}" "${i}" "main_ip")"

            text="sflow {\n
                polling = 30\n
                sampling = 10\n
                sampling.100M = 10\n
                sampling.1G = 10\n
                sampling.10G = 10\n
                sampling.40G = 10\n
                collector { ip="$main_ip" udpport=6343 }\n
                psample { group=1 }
                agent = host\n
            }\n
            "
            # nflog { group=5 probability=0.1 }\n

            docker exec "$group_number"_"$rname"router tc qdisc add dev host handle ffff: ingress
            docker exec "$group_number"_"$rname"router tc filter add dev host parent ffff: matchall action sample rate 10 group 1
            # If a host is connected multiple times:
            # Since the [4] value could also be ALL we need to check if is a number
            if (( ${#router_i[@]} > 4 )) && [[ "${router_i[4]}" =~ ^[0-9]+$ ]]; then
                num_hosts="${router_i[4]}"
                for ((j=1;j<=num_hosts;j++)); do
                    docker exec "$group_number"_"$rname"router tc qdisc add dev host"$j" handle ffff: ingress
                    docker exec "$group_number"_"$rname"router tc filter add dev host"$j" parent ffff: matchall action sample rate 10 group 1
                done
            fi     
            

            echo -e $text > hsflowd.conf
            docker cp hsflowd.conf "$group_number"_"$rname"router:/etc/hsflowd.conf
            rm hsflowd.conf

            docker cp "${DIRECTORY}"/setup/start_sflow.sh "$group_number"_"$rname"router:start.sh
            docker exec "$group_number"_"$rname"router chmod +x start.sh
            docker exec "$group_number"_"$rname"router chown root:root start.sh
            docker exec "$group_number"_"$rname"router ./start.sh

        done
    fi
done
