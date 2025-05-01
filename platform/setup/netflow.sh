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
    group_layer2_switches="${group_k[5]}"
    group_layer2_hosts="${group_k[6]}"
    group_layer2_links="${group_k[7]}"

    if [ "${group_as}" != "IXP" ];then

        # echo docker exec -it "$group_number"_netflow pkill tcpdump
        # docker exec -it "$group_number"_netflow pkill tcpdump

        # docker exec -d "$group_number"_netflow timeout 3m tcpdump -ni any -Q in port 9996 -w netflow_g"${group_number}".pcap
        # sleep 1

        readarray routers < "${DIRECTORY}"/config/$group_router_config
        n_routers=${#routers[@]}

        # we skip all ASes with a single router, no flow export for now
        if [ "$n_routers" -eq 1 ]; then
            continue
        fi

        for ((i=0;i<n_routers;i++)); do
            router_i=(${routers[$i]})
            rname="${router_i[0]}"
            property1="${router_i[1]}"
            property2="${router_i[2]}"
            htype=$(echo $property2 | cut -d ':' -f 1)
            dname=$(echo $property2 | cut -d ':' -f 2)

            main_ip="$(subnet_netflow_collector "${group_number}" "${i}" "main_ip")"
            docker exec -d "$group_number"_"$rname"router pkill softflowd

            sleep 1

            # docker exec -it "$group_number"_"$rname"router ip -o link | grep ether | awk '{ print $2";"$17}'
            interfaces=$(docker exec "$group_number"_"$rname"router ip -o link show) 
            # echo "$group_k"
            # echo "$interfaces"
            j=0
            while IFS= read -r line; do
                # echo "$line"

                iface=$(echo "$line" | awk -F': ' '{print $2}')

                # TODO: check with tunnel lab
                if  [[ $iface == lo ]] || [[ $iface == netflow* ]] || [[ $iface == sit* ]] || [[ $iface == gre* ]] || [[ $iface == gretap* ]] || [[ $iface == erspan* ]]; then
                    continue
                fi

                j=$((j+1))

                # filter out, only relevant interfaces
                mac_address=$(echo "$line" | grep -oP 'ether \K[\w:]+')
                iface_base=${iface%%@*}
                
                # echo "$rname" "$iface" "$iface_base" "$mac_address"
                docker exec "$group_number"_"$rname"router softflowd -i "$iface_base" -n "$main_ip":9996 -p /var/run/softflowd"$j".pid -t general=5s -m 1 -v 10 -T ether ether src "$mac_address" or ether dst "$mac_address"

            done  <<< "$interfaces"

        done
    fi
done


# for ((k=0;k<group_numbers;k++)); do
#     group_k=(${groups[$k]})
#     group_number="${group_k[0]}"
#     group_as="${group_k[1]}"
#     group_config="${group_k[2]}"
#     group_router_config="${group_k[3]}"
#     group_layer2_switches="${group_k[5]}"
#     group_layer2_hosts="${group_k[6]}"
#     group_layer2_links="${group_k[7]}"

#     if [ "${group_as}" != "IXP" ];then
#         readarray routers < "${DIRECTORY}"/config/$group_router_config
#         n_routers=${#routers[@]}

#         python3 "${DIRECTORY}"/traffic.py "${n_routers}" 6

#         for ((i=0;i<n_routers;i++)); do
#             router_i=(${routers[$i]})
#             rname="${router_i[0]}"
#             property1="${router_i[1]}"
#             property2="${router_i[2]}"
#             htype=$(echo $property2 | cut -d ':' -f 1)
#             dname=$(echo $property2 | cut -d ':' -f 2)

#             docker cp "${DIRECTORY}"/cmd_"$i".sh "$group_number"_"$rname"host:cmd.sh
#             docker exec -it "$group_number"_"$rname"host chmod +x cmd.sh
#             docker exec -d "$group_number"_"$rname"host ./cmd.sh

#             rm "${DIRECTORY}"/cmd_"$i".sh
#         done
#     fi
# done
