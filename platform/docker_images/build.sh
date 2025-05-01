#!/bin/bash

set -o errexit
set -o pipefail
set -o nounset

arch=$(dpkg --print-architecture)
if [[ $arch == *"arm"* ]]; then
  cp docker_images/base/Dockerfile.arm docker_images/base/Dockerfile
fi

images=(base base_supervisor host router ixp ssh dns switch matrix vpn webserver ubuntu_host)

for image in "${images[@]}"; do
    echo 'Build '$image
    docker build --tag="d_${image}" "docker_images/${image}/"
done

docker_name=mini_internet_api

for image in "${images[@]:2}"; do
    docker tag "d_${image}" "${docker_name}/d_${image}"
done
