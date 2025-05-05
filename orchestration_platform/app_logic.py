import io
import ipaddress
import json
import os
import random  # alternatively use uuid, but thats one more library and its probably overkill
import string
import tarfile
import tempfile
import time
from datetime import datetime, timedelta
from random import randrange

import config
import docker
import lab_parser
from fastapi import FastAPI, HTTPException, Query

client = docker.from_env()


class NodeID:
    """A class to represent a node's identification information including name, container name, and container object."""

    def __init__(self, supplied_name, supplied_containername, supplied_container):
        self.name = supplied_name
        self.containername = supplied_containername
        self.container = supplied_container


def calculate_endtime(duration):
    """Calculate the end time by adding duration seconds to the current time.

    Args:
        duration: Number of seconds to add to current time

    Returns:
        str: Formatted datetime string of the end time
    """
    # Get the current time as starttime
    starttime = datetime.now()
    # Add duration (in seconds) to starttime to get endtime
    endtime = starttime + timedelta(seconds=duration)
    # Format endtime as a string
    return endtime.strftime("%Y-%m-%d %H:%M:%S")


def generate_random_id(length: int = 8):
    """Generate a random alphanumeric ID of specified length.

    Args:
        length: Length of the ID to generate (default 8)

    Returns:
        str: Random alphanumeric string
    """
    return "".join(random.choices(string.ascii_letters + string.digits, k=length))


def validate_and_get_NodeID(node: str, nodetype: str):
    """
    Validates `node` against LAB_NAMES and the NodeID for node.
    Raises an HTTPException if validation fails.
    """
    if node not in config.LAB_NAMES:
        raise HTTPException(status_code=404, detail=f"Invalid node: {node}")

    node_container_name = f"{config.LAB_PREFIX}_{node}{nodetype}"
    node_container = client.containers.get(node_container_name)

    node_obj = NodeID(node, node_container_name, node_container)
    return node_obj


# Wrapper to return a tuple of src and dst NodeIDs, since usually 2 are required
def validate_and_get_NodeIDs(src: str, dst: str, nodetype: str = "router"):
    """
    Validates `src` and `dst` against LAB_NAMES and returns a tuple with the NodeID for src and dst.
    Raises an HTTPException if validation fails.
    """
    src_obj = validate_and_get_NodeID(src, nodetype)
    dst_obj = validate_and_get_NodeID(dst, nodetype)
    return src_obj, dst_obj


def archive_script(scriptpath):
    """Create a tar archive of a script file.

    Args:
        scriptpath: Path to the script file to archive

    Returns:
        io.BytesIO: Bytes stream containing the tar archive
    """
    tar_stream = io.BytesIO()
    with tarfile.open(fileobj=tar_stream, mode="w") as tar:
        tar.add(scriptpath, arcname=os.path.basename(scriptpath))
    tar_stream.seek(0)
    return tar_stream


def strip_whitespace(data):
    """Recursively strip whitespace from strings in a data structure.

    Args:
        data: Input data (dict, list, or str) to process

    Returns:
        The input data with all strings stripped of whitespace
    """
    if isinstance(data, dict):
        return {key.strip(): strip_whitespace(value) for key, value in data.items()}
    elif isinstance(data, list):
        return [strip_whitespace(item) for item in data]
    elif isinstance(data, str):
        return data.strip()
    else:
        return data


def parse_link_parameters(cmd_output: str, src: NodeID, dst: NodeID) -> dict:
    """
    Parse the output of `tc qdisc show` to extract loss rate and delay.
    Returns a dictionary with keys 'loss' and 'delay'.
    """
    result = {
        "loss": config.LAB_LINKS[frozenset({src.name, dst.name})]["loss"],
        "delay": config.LAB_LINKS[frozenset({src.name, dst.name})]["delay"],
        "bandwidth": config.LAB_LINKS[frozenset({src.name, dst.name})]["bandwidth"],
        "burst": config.LAB_LINKS[frozenset({src.name, dst.name})]["burst"],
        "buffer": config.LAB_LINKS[frozenset({src.name, dst.name})]["buffer"],
    }
    for line in cmd_output.splitlines():
        if "netem" in line:
            parts = line.split()
            for i, part in enumerate(parts):
                if part == "loss" and i + 1 < len(parts):
                    loss_str = parts[i + 1]
                    # Check if the loss string ends with a percentage sign
                    # if loss_str.endswith("%"):
                    #     # Extract the numeric value and convert to float
                    #     loss_str = loss_str[:-1]
                    #     result["loss"] = float(loss_str)
                    result["loss"] = loss_str
                    # result["loss"] = loss_str
                elif part == "delay" and i + 1 < len(parts):
                    delay_str = parts[i + 1]
                    result["delay"] = delay_str
                    # if delay_str.endswith("ms"):
                    #     result["delay"] = float(delay_str[:-2])
                    # elif delay_str.endswith("s"):
                    #     result["delay"] = float(delay_str[:-1]) * 1000
        elif "tbf" in line:
            parts = line.split()
            for i, part in enumerate(parts):
                if part == "rate" and i + 1 < len(parts):
                    rate_str = parts[i + 1]
                    result["bandwidth"] = rate_str
                    # if rate_str.endswith("Mbit"):
                    #     result["bandwidth"] = float(rate_str[:-4])
                elif part == "burst" and i + 1 < len(parts):
                    burst_str = parts[i + 1]
                    result["burst"] = burst_str
                    # if burst_str.endswith("Kb"):
                    #     result["burst"] = float(burst_str[:-2])
                    # elif burst_str.endswith("b"):
                    #     result["burst"] = float(burst_str[:-1])
                elif part == "lat" and i + 1 < len(parts):
                    buffer_str = parts[i + 1]
                    result["buffer"] = buffer_str
                    # if buffer_str.endswith("ms"):
                    #     result["buffer"] = float(buffer_str[:-2])
    return result


def save_current_config(configuration, node: str):
    """Save the current configuration to a timestamped file.

    Args:
        configuration: Configuration text to save
        node: Node name to include in filename
    """
    time = datetime.now()  # noqa: F811
    timestr = time.strftime("%Y-%m-%d_%H-%M-%S")
    # Open a file in write mode ('w')
    with open(f"{config.LOGS_DIR}/{timestr}_{node}.txt", "w") as file:
        # Write the string to the file
        file.write(configuration)


def get_interface_from_to(src: NodeID, dst: NodeID):
    """Get the interface name between two nodes.

    Args:
        src: Source NodeID object
        dst: Destination NodeID object

    Returns:
        str: Interface name
    """
    # Check if the link exists
    if frozenset({src.name, dst.name}) not in config.LAB_LINKS:
        raise Exception(f"No link exists between {src.name} and {dst.name}")
    # Utilize DNS to automatically get the proper iface
    # TODO: Cache the responses to avoid unnecessary lookups
    target_IP = config.IPS[dst.name]
    print("target IP: ", target_IP)
    command = f"/bin/bash -c 'ip -o route get {target_IP} '"
    print(command)
    print(src.containername)

    exec_result = src.container.exec_run(command)
    result = exec_result.output.decode("utf-8").split()
    print(result)
    # The interface is the 5th element in the output
    iface = result[4]
    return iface


def is_valid_ip(ip_str):
    """Check if a string is a valid IP address.

    Args:
        ip_str: String to validate

    Returns:
        bool: True if valid IP, False otherwise
    """
    try:
        ipaddress.ip_address(ip_str)
        return True
    except ValueError:
        return False


def is_valid_network(network_str):
    """Check if a string is a valid IP network with prefix.

    Args:
        network_str: String to validate

    Returns:
        bool: True if valid network, False otherwise
    """
    try:
        ipaddress.ip_network(network_str, strict=True)
        return True
    except ValueError:
        return False


def is_valid_ip_with_prefix(ip_str):
    """Check if a string is a valid IP address with prefix.

    Args:
        ip_str: String to validate

    Returns:
        bool: True if valid IP with prefix, False otherwise
    """
    try:
        # Try to parse the string as an IPv4 or IPv6 network
        ipaddress.ip_network(ip_str, strict=False)
        return True
    except ValueError:
        return False


def clean_frr_config(frr_config):
    """Clean FRR configuration by removing lines that aren't readable by FRR.
    The default FRR config contains some separators and extra lines to make it more human readable,
    this function strips those.

    Args:
        frr_config: Human readable FRR configuration string(from /etc/frr/frr.conf)

    Returns:
        str: Cleaned FRR configuration
    """
    lines = frr_config.splitlines()
    exclude_lines = [
        "Building configuration...",
        "Current configuration:",
        "!",
        "end",
    ]
    cleaned_lines = [line for line in lines if line.strip() not in exclude_lines]
    return "\n".join(cleaned_lines)


def apply_frr_config_at(node: NodeID, frr_config: str):
    """Apply FRR configuration to a node.

    Args:
        node: NodeID object to apply config to
        frr_config: Configuration string to apply

    Raises:
        Exception: If configuration application fails
    """
    # Even though frr can load the default config from disk when starting, it unfortunately doesnt provide any API to reload it from disk.
    # The available APIs can only be to load "pure" config files that do not include headers (and "!" separators)
    # like they are written in the default config file.
    # Therefore we have to resort to some ugly hack like this
    cleaned_config = clean_frr_config(frr_config)
    command = f"sh -c 'echo \"{cleaned_config}\" > /etc/frr/frr_new.conf  && /usr/lib/frr/frr-reload.py --reload /etc/frr/frr_new.conf && rm /etc/frr/frr_new.conf'"
    result = node.container.exec_run(command, tty=True)
    if result[0] != 0:
        raise Exception(f"Could not apply config in {node.name}, detail: {result[1]}")
    # print(f"File contents written to {container_file_path} in container {container_id}")
    # An alternative way to apply a new config would be to invoke /usr/lib/frr/frr-reload.py on the router container

    return


def get_IPS(nodetype: str):
    """Gets the highest IP for each device using DNS and returns them in a dict"""
    updated_ips = {}
    for device in config.LAB_NAMES:
        if nodetype == "host":
            dns_name = "host." + str(device) + f".group{config.LAB_PREFIX}"
        elif nodetype == "router":
            dns_name = str(device) + f".group{config.LAB_PREFIX}"
        else:
            raise Exception(f"No such nodetype: {nodetype}")
        # host containers dont have dig installed, so we query on the router.
        # as a sidenote: we could also directly check the interface IPs using docker exec
        node = validate_and_get_NodeID(device, "router")
        result = node.container.exec_run(f"dig +short {dns_name}")
        ip_list = result.output.decode("utf-8").splitlines()
        # TODO: In case a device has its interfaces currently down, this way of retrieving the IP will not work
        # Catch this and possibly fall back to lab parsing IP
        if ip_list:
            # print(f"IPs for {device}: {ip_list}")
            ip_objects = []
            for ip in ip_list:
                try:
                    ip_objects.append(ipaddress.ip_address(ip))
                except ValueError:
                    # If the IP address is not valid, we skip it
                    print(f"Invalid IP address {ip}")
                    pass
            # print(ip_objects)
            highest_ip = max(ip_objects)
            updated_ips[device] = str(highest_ip)
            print(f"Got IP for {device}{nodetype} to {updated_ips[device]}")
    return updated_ips


def extract_and_process_logs(container, archive_path, local_file_path):
    stream, _ = container.get_archive(archive_path)
    with tempfile.TemporaryFile() as temp_file:
        for chunk in stream:
            temp_file.write(chunk)
        temp_file.seek(0)
        with tarfile.open(fileobj=temp_file) as tar:
            tar.extractall(path=tempfile.gettempdir())
            extracted_file_path = os.path.join(
                tempfile.gettempdir(), "all_frr_logs.log"
            )
            # Process the extracted file as needed


# Begin actual request logic


def change_lab(request: config.ChangeLabRequest):
    """Change the current lab configuration.

    Args:
        request: ChangeLabRequest object with lab details

    Returns:
        str: Success message

    Raises:
        HTTPException: If lab change fails
    """
    try:
        # Only start changing global variables once we know that a correct lab was requested, above function would fail if not
        # Pretty sure we dont need the temporary tuple but better safe than sorry
        (new_LAB_PREFIX, new_LAB_NAMES) = lab_parser.get_labnames(
            request.lab_name, request.selected_AS
        )
        config.CURR_LAB = request.lab_name
        (config.LAB_PREFIX, config.LAB_NAMES) = (new_LAB_PREFIX, new_LAB_NAMES)
        config.IPS = get_IPS("router")
        # Potentially also actually change the running network lab, probably something like:
        # this command would only work if the API is running natively
        # startub_lab_path = f"{path_to_repo}/platform/startup.sh"
        # result = subprocess.run([startup_lab_path, CURR_LAB], capture_output=True, text=True
        return f"Successfully changed to lab {config.CURR_LAB}"
    except FileNotFoundError:
        raise HTTPException(status_code=404, detail="Requested lab not found")  # noqa: B904


def add_loss(request: config.AddLossRequest):
    """Add packet loss to a network link.

    Args:
        request: AddLossRequest object with link details

    Returns:
        dict: Command execution results

    Raises:
        HTTPException: If operation fails
    """
    try:
        # Validate and get identifiers
        src, dst = validate_and_get_NodeIDs(request.src, request.dst)
        current_params = check_link_state(src.name, dst.name)

        # TODO: error handing
        loss_rate = request.loss_rate
        interface = get_interface_from_to(src, dst)

        cmd = f"""/bin/bash -c 'tc qdisc del dev {interface} root ; \
        tc qdisc add dev {interface} root handle 1:0 netem delay {current_params["delay"]} loss {loss_rate}% ; \n \
        tc qdisc add dev {interface} parent 1:1 handle 10: tbf rate {current_params["bandwidth"]} burst {current_params["burst"]} latency {current_params["buffer"]}'"""

        # Execute the command in the container
        exec_result = src.container.exec_run(cmd)

        if exec_result.exit_code != 0:
            raise Exception(
                {
                    "exit_code": exec_result.exit_code,
                }
            )
        # Return the output of the command
        return {
            "output": exec_result.output.decode("utf-8"),
            "exit_code": exec_result.exit_code,
        }

    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))  # noqa: B904
    except docker.errors.NotFound:  # type: ignore
        raise HTTPException(status_code=404, detail="Container not found")  # noqa: B904
    except docker.errors.APIError as e:  # type: ignore
        raise HTTPException(status_code=500, detail="Docker: " + str(e))  # noqa: B904


# We could check if there already is loss on the specified link but ultimately it doesnt change the outcome so for now I don't
def rm_loss(request: config.RemoveChangeRequest):
    """Remove packet loss from a network link.

    Args:
        request: RemoveChangeRequest object with link details

    Returns:
        dict: Command execution results

    Raises:
        HTTPException: If operation fails
    """
    try:
        # Validate and get container names
        src, dst = validate_and_get_NodeIDs(request.src, request.dst)
        current_params = check_link_state(src.name, dst.name)
        interface = get_interface_from_to(src, dst)

        cmd = f"""/bin/bash -c '
        tc qdisc del dev {interface} root ; \
        tc qdisc add dev {interface} root handle 1:0 netem delay {current_params["delay"]}\n \
        tc qdisc add dev {interface} parent 1:1 handle 10: tbf rate {current_params["bandwidth"]} burst {current_params["burst"]} latency {current_params["buffer"]}'"""

        # Execute the command in the container
        exec_result = src.container.exec_run(cmd)

        if exec_result.exit_code != 0:
            raise Exception(
                {
                    "output": exec_result.output.decode("utf-8"),
                    "exit_code": exec_result.exit_code,
                }
            )
        # Return the output of the command
        return {
            "output": exec_result.output.decode("utf-8"),
            "exit_code": exec_result.exit_code,
        }

    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))  # noqa: B904
    except docker.errors.NotFound:  # type: ignore
        raise HTTPException(status_code=404, detail="Container not found")  # noqa: B904
    except docker.errors.APIError as e:  # type: ignore
        raise HTTPException(status_code=500, detail="Docker: " + str(e))  # noqa: B904


def add_delay(request: config.AddDelayRequest):
    """Add delay to a network link.

    Args:
        request: AddDelayRequest object with link details

    Returns:
        dict: Command execution results

    Raises:
        HTTPException: If operation fails
    """
    try:
        # Validate and get identifiers
        src, dst = validate_and_get_NodeIDs(request.src, request.dst)
        current_params = check_link_state(src.name, dst.name)

        # TODO: error handing
        delay = request.delay
        # Get the container object
        interface = get_interface_from_to(src, dst)
        cmd = f"""/bin/bash -c 'tc qdisc del dev {interface} root ; \
        tc qdisc add dev {interface} root handle 1:0 netem delay {delay}ms loss {current_params["loss"]} ; \n \
        tc qdisc add dev {interface} parent 1:1 handle 10: tbf rate {current_params["bandwidth"]} burst {current_params["burst"]} latency {current_params["buffer"]}'"""

        # Execute the command in the container
        exec_result = src.container.exec_run(cmd)

        if exec_result.exit_code != 0:
            raise Exception(
                {
                    "exit_code": exec_result.exit_code,
                }
            )
        # Return the output of the command
        return {
            "output": exec_result.output.decode("utf-8"),
            "exit_code": exec_result.exit_code,
        }

    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))  # noqa: B904
    except docker.errors.NotFound:  # type: ignore
        raise HTTPException(status_code=404, detail="Container not found")  # noqa: B904
    except docker.errors.APIError as e:  # type: ignore
        raise HTTPException(status_code=500, detail="Docker: " + str(e))  # noqa: B904


def rm_delay(request: config.RemoveChangeRequest):
    """Remove delay from a network link.

    Args:
        request: RemoveChangeRequest object with link details

    Returns:
        dict: Command execution results

    Raises:
        HTTPException: If operation fails
    """
    try:
        # Validate and get container names
        src, dst = validate_and_get_NodeIDs(request.src, request.dst)
        current_params = check_link_state(src.name, dst.name)

        # it is set in the network setup and should be parsed from there
        interface = get_interface_from_to(src, dst)
        cmd = f"""/bin/bash -c '
        tc qdisc del dev {interface} root ; \
        tc qdisc add dev {interface} root handle 1:0 netem loss {current_params["loss"]} delay {config.LAB_LINKS[frozenset({src.name, dst.name})]["delay"]}\n \
        tc qdisc add dev {interface} parent 1:1 handle 10: tbf rate {current_params["bandwidth"]} burst {current_params["burst"]} latency {current_params["buffer"]}'"""

        # Execute the command in the container
        exec_result = src.container.exec_run(cmd)

        if exec_result.exit_code != 0:
            raise Exception(
                {
                    "output": exec_result.output.decode("utf-8"),
                    "exit_code": exec_result.exit_code,
                }
            )
        # Return the output of the command
        return {
            "output": exec_result.output.decode("utf-8"),
            "exit_code": exec_result.exit_code,
        }

    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))  # noqa: B904
    except docker.errors.NotFound:  # type: ignore
        raise HTTPException(status_code=404, detail="Container not found")  # noqa: B904
    except docker.errors.APIError as e:  # type: ignore
        raise HTTPException(status_code=500, detail="Docker: " + str(e))  # noqa: B904


def single_flow(request: config.GenFlowRequest):
    """Generate a single network flow between hosts.

    Args:
        request: GenFlowRequest object with flow details

    Returns:
        dict: Flow ID and execution details

    Raises:
        HTTPException: If operation fails
    """
    try:
        # Validate and get container names
        src, dst = validate_and_get_NodeIDs(request.src, request.dst, "host")

        # TODO: error handing
        bandwidth = request.bandwidth
        duration = request.duration
        is_tcp = request.is_tcp

        # Get an id for the caller to refer to the request
        # use this as filename for the status
        id = generate_random_id()
        # Actually do the thing,
        port = randrange(1024, 65535)
        udp_str = "-u " if not is_tcp else ""
        server_cmd = f"iperf3 -D -B {config.IPS[dst.name]} -s -p {port} -1"
        client_cmd = f"iperf3 -J --logfile {id}.json -c {config.IPS[dst.name]} -t {duration}s -b {bandwidth}k -B {config.IPS[src.name]} -p {port} {udp_str}&"
        # print(client_cmd)

        exec_result = dst.container.exec_run(server_cmd)
        if exec_result.exit_code != 0:
            raise Exception(
                {
                    "output": exec_result.output.decode("utf-8"),
                    "exit_code": exec_result.exit_code,
                }
            )

        exec_id = client.api.exec_create(src.containername, client_cmd)

        config.EVENT_DATABASE[id] = {
            "exec_id": exec_id["Id"],
            "container": src.containername,
            "json": True,
            "endtime": calculate_endtime(duration),
        }
        client.api.exec_start(exec_id, detach=True)
        return {"ID": id}

    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))  # noqa: B904
    except docker.errors.NotFound:  # type: ignore
        raise HTTPException(status_code=404, detail="Container not found")  # noqa: B904
    except docker.errors.APIError as e:  # type: ignore
        raise HTTPException(status_code=500, detail="Docker: " + str(e))  # noqa: B904


def change_ospf_weight(request: config.ChangeOSPFCostRequest):
    """Change OSPF link cost between routers.

    Args:
        request: ChangeOSPFCostRequest object with link details

    Returns:
        dict: Command execution results

    Raises:
        HTTPException: If operation fails
    """
    try:
        # Validate and get container names
        src, dst = validate_and_get_NodeIDs(request.src, request.dst)
        cost = request.cost
        cmd = f'''vtysh
        -c "configure terminal"
        -c "interface {get_interface_from_to(src, dst)}"
        -c "ip ospf cost {cost}"
        -c "exit"
        -c "exit"
        -c "write memory"'''

        exec_result = src.container.exec_run(cmd)
        if exec_result.exit_code != 0:
            raise Exception(
                {
                    "output": exec_result.output.decode("utf-8"),
                    "exit_code": exec_result.exit_code,
                }
            )
        # Get the current config and save it to disk
        config = get_current_config(src.name)["output"]
        save_current_config(config, src.name)
        return {
            "output": exec_result.output.decode("utf-8"),
            "exit_code": exec_result.exit_code,
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))  # noqa: B904
    except docker.errors.NotFound:  # type: ignore
        raise HTTPException(status_code=404, detail="Container not found")  # noqa: B904
    except docker.errors.APIError as e:  # type: ignore
        raise HTTPException(status_code=500, detail="Docker: " + str(e))  # noqa: B904


def execute_script_in_container(request: config.scriptRequest):
    """
    Endpoint to save a bash command to a script, copy it into a container,
    and execute it.
    """
    try:
        # Step 1: Save the command to a temporary script file
        with tempfile.NamedTemporaryFile(
            mode="w", delete=False, suffix=".sh"
        ) as temp_script:
            temp_script.write(f"#!/bin/bash\n{request.cmd}")
            temp_script_path = temp_script.name

        # Ensure the script is executable
        os.chmod(temp_script_path, 0o755)

        # Step 2: Archive script
        tar_stream = archive_script(temp_script_path)
        # Step 3: Copy the script into the container
        container = client.containers.get(request.container_name)
        container.put_archive(path="/tmp", data=tar_stream.read())
        # Step 3: Execute the script inside the container
        exec_id = container.exec_run(f"/tmp/{os.path.basename(temp_script_path)}")
        output = exec_id.output.decode("utf-8")

        # Step 4: Clean up the temporary script file
        os.remove(temp_script_path)

        return {"output": output}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))  # noqa: B904
    except docker.errors.NotFound:  # type: ignore
        raise HTTPException(status_code=404, detail="Container not found")  # noqa: B904
    except docker.errors.APIError as e:  # type: ignore
        raise HTTPException(status_code=500, detail="Docker: " + str(e))  # noqa: B904


def get_all_configs():
    """Get configurations for all nodes in the lab.

    Returns:
        dict: Configurations for all nodes

    Raises:
        HTTPException: If operation fails
    """
    try:
        output = {}
        for node_name in config.LAB_NAMES:
            output[node_name] = get_current_config(node_name)["output"]
        return {"output": output}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))  # noqa: B904
    except docker.errors.NotFound:  # type: ignore
        raise HTTPException(status_code=404, detail="Container not found")  # noqa: B904
    except docker.errors.APIError as e:  # type: ignore
        raise HTTPException(status_code=500, detail="Docker: " + str(e))  # noqa: B904


def get_current_config(router: str):
    """Get the currently running FRR config at the specified router"""
    try:
        cmd = '''vtysh -c  "show run"'''
        node = validate_and_get_NodeID(router, "router")

        exec_result = node.container.exec_run(cmd)
        if exec_result.exit_code != 0:
            raise Exception(
                {
                    "exit_code": exec_result.exit_code,
                }
            )

        output_dict = exec_result.output.decode("utf-8")
        # output_dict = json.loads(output_dict)
        # output = strip_whitespace(output_dict)
        return {"output": output_dict}

    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))  # noqa: B904
    except docker.errors.NotFound:  # type: ignore
        raise HTTPException(status_code=404, detail="Container not found")  # noqa: B904
    except docker.errors.APIError as e:  # type: ignore
        raise HTTPException(status_code=500, detail="Docker: " + str(e))  # noqa: B904


def get_status(cmd_id: str):
    """Get status of a command execution.

    Args:
        cmd_id: Command ID to check

    Returns:
        dict: Status information

    Raises:
        HTTPException: If command ID not found or operation fails
    """
    try:
        # Inspect the exec instance
        exec_id = config.EVENT_DATABASE[cmd_id]["exec_id"]
        # container_name = event_database[cmd_id]["container"]
        exec_info = client.api.exec_inspect(exec_id)
        status = exec_info["Running"]

        if status:
            return {"status": "Exec command is still running..."}
        else:
            return {"exit_code": exec_info["ExitCode"]}
    except KeyError:
        raise HTTPException(status_code=404, detail="No such ID")  # noqa: B904
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))  # noqa: B904
    except docker.errors.NotFound:  # type: ignore
        raise HTTPException(status_code=404, detail="Container not found")  # noqa: B904
    except docker.errors.APIError as e:  # type: ignore
        raise HTTPException(status_code=500, detail="Docker: " + str(e))  # noqa: B904


def get_output(cmd_id: str):
    """Returns the output of the command that is referred to by the supplied cmd_id"""
    try:
        # Inspect the exec instance
        exec_id = config.EVENT_DATABASE[cmd_id]["exec_id"]
        container_name = config.EVENT_DATABASE[cmd_id]["container"]
        exec_info = client.api.exec_inspect(exec_id)

        # Command has finished, check the output
        container_obj = client.containers.get(container_name)
        file_ending = "json" if config.EVENT_DATABASE[cmd_id]["json"] else "txt"
        exec_result = container_obj.exec_run(f"cat {cmd_id}.{file_ending}")
        # Decode the byte string to a regular string
        output_str = exec_result[1].decode("utf-8")
        # print(output_str)
        # Parse the JSON string into a Python dictionary
        output_dict = json.loads(output_str)

        # Now `output_dict` contains the JSON data as a Python dictionary
        stripped_dict = strip_whitespace(output_dict)
        # Return the output of the command
        # Its quite a lot now with iperf, prolly should eventually find a better way to display results(eg -J for json output)
        return {"output": stripped_dict, "exit_code": exec_result.exit_code}
        # Command has finished
        return {
            "status": "Exec command has finished",
            "exit_code": exec_info["ExitCode"],
        }
    except KeyError:
        raise HTTPException(status_code=404, detail="No such ID")  # noqa: B904
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))  # noqa: B904
    except docker.errors.NotFound:  # type: ignore
        raise HTTPException(status_code=404, detail="Container not found")  # noqa: B904
    except docker.errors.APIError as e:  # type: ignore
        raise HTTPException(status_code=500, detail="Docker: " + str(e))  # noqa: B904


def check_link_state(src: str, dst: str):
    """Check the current state (loss, delay, bandwidth, burst, buffer) of a network link.

    Args:
        src: Source node name
        dst: Destination node name

    Returns:
        dict: Current link parameters (loss, delay, bandwidth, burst, buffer)

    Raises:
        HTTPException: If operation fails
    """
    # Should be extended to also reflect new kinds of status changes, once theyre implemented
    try:
        # Validate and get identifiers
        src, dst = validate_and_get_NodeIDs(src, dst, "router")  # type: ignore

        # Command to check the current parameters
        cmd = f"/bin/bash -c 'tc qdisc show dev {get_interface_from_to(src, dst)}'"  # type: ignore

        # Execute the command in the container
        exec_result = src.container.exec_run(cmd)  # type: ignore

        if exec_result.exit_code != 0:
            raise Exception(
                {
                    "output": exec_result.output.decode("utf-8"),
                    "exit_code": exec_result.exit_code,
                }
            )

        # Parse the output to extract the parameters
        output = exec_result.output.decode("utf-8")
        # print(output)
        link_parameters = parse_link_parameters(output, src, dst)

        # Return the current parameters
        return {
            "loss": link_parameters["loss"],
            "delay": link_parameters["delay"],
            "bandwidth": link_parameters["bandwidth"],
            "burst": link_parameters["burst"],
            "buffer": link_parameters["buffer"],
        }

    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))  # noqa: B904
    except docker.errors.NotFound:  # type: ignore
        raise HTTPException(status_code=404, detail="Container not found")  # noqa: B904
    except docker.errors.APIError as e:  # type: ignore
        raise HTTPException(status_code=500, detail="Docker: " + str(e))  # noqa: B904


def start_collection():
    """Start packet collection on the netflow container.

    Returns:
        dict: Collection ID

    Raises:
        HTTPException: If operation fails
    """
    try:
        time = datetime.now()
        timestr = time.strftime("%Y-%m-%d_%H-%M-%S")

        id = generate_random_id()

        cmd = f"""/bin/bash -c 'tcpdump -i any -w {timestr}.pcap\n'"""

        # Get netflow contaner of current topology
        netflow_containername = f"{config.LAB_PREFIX}_netflow"
        exec_id = client.api.exec_create(netflow_containername, cmd)

        config.EVENT_DATABASE[id] = {
            "exec_id": exec_id["Id"],
            "container": netflow_containername,
            "json": True,
            "endtime": "-1",
        }

        client.api.exec_start(exec_id, detach=True)

        return {"ID": id}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))  # noqa: B904
    except docker.errors.NotFound:  # type: ignore
        raise HTTPException(status_code=404, detail="Container not found")  # noqa: B904
    except docker.errors.APIError as e:  # type: ignore
        raise HTTPException(status_code=500, detail="Docker: " + str(e))  # noqa: B904


def stop_collection():
    """Stop packet collection on the netflow container and copy the file to the host.

    Returns:
        dict: Command execution results

    Raises:
        HTTPException: If operation fails
    """
    try:
        # Get netflow contaner of current topology
        container = client.containers.get(f"{config.LAB_PREFIX}_netflow")
        cmd = """/bin/bash -c 'pkill -SIGINT tcpdump'"""

        # Execute the command in the container
        exec_result = container.exec_run(cmd)

        # Get the list of files in the container's directory
        # FIXME: get the currently running pcap from a local variable(set when starting collection)
        file_list_cmd = "/bin/bash -c 'ls -t /'"
        file_list_result = container.exec_run(file_list_cmd)

        if file_list_result.exit_code != 0:
            raise Exception(
                f"Failed to list files in container. Command output: {file_list_result.output.decode('utf-8')}"
            )

        # Parse the output to find the latest pcap file
        files = file_list_result.output.decode("utf-8").splitlines()
        latest_pcap = next((file for file in files if file.endswith(".pcap")), None)

        if not latest_pcap:
            raise Exception("No pcap file found in the container.")

        # Copy the latest pcap file to the host
        archive_path = f"/{latest_pcap}"
        local_file_path = os.path.join(config.LOGS_DIR, latest_pcap)

        stream, _ = container.get_archive(archive_path)
        with open(local_file_path, "wb") as local_file:
            for chunk in stream:
                local_file.write(chunk)
        if exec_result.exit_code != 0:
            raise Exception(
                {
                    "exit_code": exec_result.exit_code,
                }
            )
        # Return the output of the command
        return {
            "output": exec_result.output.decode("utf-8"),
            "exit_code": exec_result.exit_code,
        }

    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))  # noqa: B904
    except docker.errors.NotFound:  # type: ignore
        raise HTTPException(status_code=404, detail="Container not found")  # noqa: B904
    except docker.errors.APIError as e:  # type: ignore
        raise HTTPException(status_code=500, detail="Docker: " + str(e))  # noqa: B904


def snmp_param(host: str, oid: str = ""):
    """Query SNMP parameters from a host.

    Args:
        host: Hostname to query
        oid: Optional OID to query (default empty)

    Returns:
        dict: SNMP query results

    Raises:
        HTTPException: If operation fails
    """
    try:
        # Get netflow contaner of current topology
        container = client.containers.get(f"{config.LAB_PREFIX}_netflow")
        host_ip = lab_parser.get_snmp_ips()[host]
        cmd = f"""/bin/bash -c 'snmpwalk -mALL -v 2c -c public {host_ip} {oid}'"""

        # Execute the command in the container
        exec_result = container.exec_run(cmd)
        if exec_result.exit_code != 0:
            raise Exception(
                {
                    "exit_code": exec_result.exit_code,
                }
            )
        # Return the output of the command
        return {
            "output": exec_result.output.decode("utf-8"),
            "exit_code": exec_result.exit_code,
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))  # noqa: B904
    except docker.errors.NotFound:  # type: ignore
        raise HTTPException(status_code=404, detail="Container not found")  # noqa: B904
    except docker.errors.APIError as e:  # type: ignore
        raise HTTPException(status_code=500, detail="Docker: " + str(e))  # noqa: B904


def add_static_route(request: config.staticRouteRequest):
    """Add a static route to a router.

    Args:
        request: staticRouteRequest object with route details

    Returns:
        dict: Command execution results

    Raises:
        HTTPException: If operation fails
    """
    try:
        # Validate and get container
        node = validate_and_get_NodeID(request.node, "router")
        destination = request.destination
        next_hop = request.next_hop
        if not is_valid_ip(next_hop):
            next_hop = config.IPS[next_hop]
        cmd = f'''vtysh
        -c "configure terminal"
        -c "ip route {destination} {next_hop}"
        -c "end"
        -c "write memory"'''

        exec_result = node.container.exec_run(cmd)
        if exec_result.exit_code != 0:
            raise Exception(
                {
                    "output": exec_result.output.decode("utf-8"),
                    "exit_code": exec_result.exit_code,
                }
            )
        # Get the current config and save it to disk
        frr_config = get_current_config(node.name)["output"]
        save_current_config(frr_config, node.name)
        return {
            "output": exec_result.output.decode("utf-8"),
            "exit_code": exec_result.exit_code,
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))  # noqa: B904
    except docker.errors.NotFound:  # type: ignore
        raise HTTPException(status_code=404, detail="Container not found")  # noqa: B904
    except docker.errors.APIError as e:  # type: ignore
        raise HTTPException(status_code=500, detail="Docker: " + str(e))  # noqa: B904


def rm_static_route(request: config.staticRouteRequest):
    """Remove a static route from a router.

    Args:
        request: staticRouteRequest object with route details

    Returns:
        dict: Command execution results

    Raises:
        HTTPException: If operation fails
    """
    try:
        # Validate and get container names
        node = validate_and_get_NodeID(request.node, "router")

        destination = request.destination
        next_hop = request.next_hop
        if not is_valid_ip(next_hop):
            next_hop = config.IPS[next_hop]
        # If the demanded static route doesnt exist frr will simply do nothing
        # so it is fine not to check if the route actually exists
        cmd = f'''vtysh
        -c "configure terminal"
        -c "no ip route {destination} {next_hop}"
        -c "end"
        -c "write memory"'''

        exec_result = node.container.exec_run(cmd)
        if exec_result.exit_code != 0:
            raise Exception(
                {
                    "output": exec_result.output.decode("utf-8"),
                    "exit_code": exec_result.exit_code,
                }
            )
        # Get the current config and save it to disk
        frr_config = get_current_config(node.name)["output"]
        save_current_config(frr_config, node.name)
        return {
            "output": exec_result.output.decode("utf-8"),
            "exit_code": exec_result.exit_code,
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))  # noqa: B904
    except docker.errors.NotFound:  # type: ignore
        raise HTTPException(status_code=404, detail="Container not found")  # noqa: B904
    except docker.errors.APIError as e:  # type: ignore
        raise HTTPException(status_code=500, detail="Docker: " + str(e))  # noqa: B904


def take_snapshot():
    """Take a snapshot of all node configurations.

    Returns:
        dict: Snapshot data and ID

    Raises:
        HTTPException: If operation fails
    """
    try:
        print("enter")
        output = get_all_configs()["output"]
        # add a timestamp to track when the snapshot was taken
        output["time"] = calculate_endtime(0)
        id = generate_random_id()
        config.SNAPSHOTS[id] = output
        return {"output": output, "id": id}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))  # noqa: B904
    except docker.errors.NotFound:  # type: ignore
        raise HTTPException(status_code=404, detail="Container not found")  # noqa: B904
    except docker.errors.APIError as e:  # type: ignore
        raise HTTPException(status_code=500, detail="Docker: " + str(e))  # noqa: B904


def apply_snapshot(request: config.ApplySnapshotRequest):
    """Apply a previously taken snapshot.

    Args:
        request: ApplySnapshotRequest with snapshot ID

    Raises:
        HTTPException: If operation fails
    """
    try:
        # obtain the snapshot dict
        snapshot = config.SNAPSHOTS[request.snapshot_id]

        ### possible optimization: (However if theres just a couple of nodes and many changes
        # , applying to all is more efficient)
        # only apply the changed configs, however if we repedeatly apply the snapshot we need some way to account for this
        # Maybe just change the saved timestamp after applying a config

        # initial_timestamp = datetime.strptime(snapshot["time"], "%Y-%m-%d %H:%M:%S")
        # # Initialize a set to store unique node names
        # nodes_after_timestamp = set()

        # # Iterate over the files in the folder
        # for filename in os.listdir(config.LOGS_DIR):
        #     if filename.endswith(".txt"):
        #         # Split the filename to extract the timestamp and node name
        #         try:
        #             timestr, node_with_extension = filename.split("_")
        #             node = node_with_extension.split(".")[0]
        #             file_timestamp = datetime.strptime(timestr, "%Y-%m-%d %H:%M:%S"):%M:     #      :%M:           # Check if the file's timestamp is after the initial timestamp
        #             if file_timestamp > initial_timestamp:
        #                 nodes_after_timestamp.add(node)
        #         except ValueError:
        #             # Skip files that don't match the expected format
        #             continue

        # # Print the nodes that have files created after the initial timestamp
        # print("Nodes with files created after the initial timestamp:")
        # for node in nodes_after_timestamp:
        #     print(node)
        #     node = validate_and_get_NodeID(node, "router")
        #     apply_frr_config_at(node, snapshot[node.name])
        # # set the time to now
        # snapshot["time"] = calculate_endtime(0)

        ###alternative impl. :
        # print(snapshot)
        # for entry in snapshot:
        #     print(type(entry))
        #     print(entry)
        #     print("\n\n\n")
        for key, value in snapshot.items():
            if key != "time" and key != "id":
                node = validate_and_get_NodeID(key, "router")
                apply_frr_config_at(node, value)
        snapshot["time"] = calculate_endtime(0)
        # if we get here everything was fine and we can return success
        return
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))  # noqa: B904
    except docker.errors.NotFound:  # type: ignore
        raise HTTPException(status_code=404, detail="Container not found")  # noqa: B904
    except docker.errors.APIError as e:  # type: ignore
        raise HTTPException(status_code=500, detail="Docker: " + str(e))  # noqa: B904


def disconnect_router(request: config.DisconnectContainerRequest):
    # alternatively use iptables to drop all traffic:
    """Disconnect a router by blocking all traffic using iptables."""
    try:
        # Validate and get container
        node_obj = validate_and_get_NodeID(request.node, "router")

        # Apply iptables rules to drop all incoming and outgoing traffic
        block_all_traffic_command = """
        iptables -A INPUT -j DROP && iptables -A OUTPUT -j DROP
        """
        exec_result = node_obj.container.exec_run(
            f'/bin/bash -c "{block_all_traffic_command}"'
        )

        if exec_result.exit_code != 0:
            raise Exception(
                f"Failed to block all traffic for router {request.node}. "
                f"Command output: {exec_result.output.decode('utf-8')}"
            )

        return {
            "status": "disconnected",
            "name": node_obj.name,
            "id": node_obj.container.id,
        }
    # """Disconnect a router by bringing down all its network interfaces."""
    # try:
    #     # Validate and get container
    #     node_obj = validate_and_get_NodeID(request.node, "router")

    #     # Step 1: Get the list of interfaces
    #     get_interfaces_command = "ip -o link show"
    #     exec_result = node_obj.container.exec_run(
    #         f'/bin/bash -c "{get_interfaces_command}"'
    #     )

    #     if exec_result.exit_code != 0:
    #         raise Exception(
    #             f"Failed to retrieve interfaces for router {request.node}. "
    #             f"Command output: {exec_result.output.decode('utf-8')}"
    #         )

    #     # Parse the list of interfaces and filter them in Python
    #     all_interfaces = exec_result.output.decode("utf-8").splitlines()
    #     interfaces = []
    #     for line in all_interfaces:
    #         iface = line.split(":")[1].strip().split("@")[0]
    #         if iface not in {"lo", "sit0", "gre0", "gretap0", "erspan0"}:
    #             interfaces.append(iface)

    #     # Step 2: Bring down each interface
    #     for iface in interfaces:
    #         bring_down_command = f"ip link set dev {iface} down"
    #         exec_result = node_obj.container.exec_run(
    #             f'/bin/bash -c "{bring_down_command}"'
    #         )

    #         if exec_result.exit_code != 0:
    #             raise Exception(
    #                 f"Failed to bring down interface {iface} on router {request.node}. "
    #                 f"Command output: {exec_result.output.decode('utf-8')}"
    #             )

    #     return {
    #         "status": "disconnected",
    #         "name": node_obj.name,
    #         "id": node_obj.container.id,
    #     }

    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))  # noqa: B904
    except docker.errors.NotFound:  # type: ignore
        raise HTTPException(status_code=404, detail="Container not found")  # noqa: B904
    except docker.errors.APIError as e:  # type: ignore
        raise HTTPException(status_code=500, detail="Docker: " + str(e))  # noqa: B904


def connect_router(request: config.DisconnectContainerRequest):
    # alternatively use iptables to unblock all traffic:
    """Reconnect a router by removing iptables rules that block traffic."""
    try:
        # Validate and get container
        node_obj = validate_and_get_NodeID(request.node, "router")

        # Remove iptables rules to unblock all traffic
        unblock_all_traffic_command = """
        iptables -D INPUT -j DROP && iptables -D OUTPUT -j DROP
        """
        exec_result = node_obj.container.exec_run(
            f'/bin/bash -c "{unblock_all_traffic_command}"'
        )

        if exec_result.exit_code != 0:
            raise Exception(
                f"Failed to unblock all traffic for router {request.node}. "
                f"Command output: {exec_result.output.decode('utf-8')}"
            )
        # if we want to ensure that shortly following commands are executed sucessfully we need to wait a bit
        # otherwise commands like ip route get fail (when changing link params)
        # time.sleep(20)
        return {
            "status": "connected",
            "name": node_obj.name,
            "id": node_obj.container.id,
        }
    # """Reconnect a router by bringing up all its network interfaces."""
    # try:
    #     # Validate and get container
    #     node_obj = validate_and_get_NodeID(request.node, "router")

    #     # Step 1: Get the list of interfaces
    #     get_interfaces_command = "ip -o link show"
    #     exec_result = node_obj.container.exec_run(
    #         f'/bin/bash -c "{get_interfaces_command}"'
    #     )

    #     if exec_result.exit_code != 0:
    #         raise Exception(
    #             f"Failed to retrieve interfaces for router {request.node}. "
    #             f"Command output: {exec_result.output.decode('utf-8')}"
    #         )

    #     # Parse the list of interfaces and filter them in Python
    #     all_interfaces = exec_result.output.decode("utf-8").splitlines()
    #     interfaces = []
    #     for line in all_interfaces:
    #         iface = line.split(":")[1].strip().split("@")[0]
    #         if iface not in {"lo", "sit0", "gre0", "gretap0", "erspan0"}:
    #             interfaces.append(iface)

    #     # Step 2: Bring up each interface
    #     for iface in interfaces:
    #         bring_up_command = f"ip link set dev {iface} up"
    #         exec_result = node_obj.container.exec_run(
    #             f'/bin/bash -c "{bring_up_command}"'
    #         )

    #         if exec_result.exit_code != 0:
    #             raise Exception(
    #                 f"Failed to bring up interface {iface} on router {request.node}. "
    #                 f"Command output: {exec_result.output.decode('utf-8')}"
    #             )

    #     return {
    #         "status": "connected",
    #         "name": node_obj.name,
    #         "id": node_obj.container.id,
    #     }

    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))  # noqa: B904
    except docker.errors.NotFound:  # type: ignore
        raise HTTPException(status_code=404, detail="Container not found")  # noqa: B904
    except docker.errors.APIError as e:  # type: ignore
        raise HTTPException(status_code=500, detail="Docker: " + str(e))  # noqa: B904


def change_FRR_config(request: config.ChangeFRRConfigRequest):
    """Execute a given, valid vtysh command on the specified router
    The command must contain any exit commands to return from submenus,
    it should not include entering and exiting the configuration terminal in vtysh.
    """
    try:
        # Validate and get container names
        node_obj = validate_and_get_NodeID(request.node, "router")
        raw_vytsh_cmd = request.cmd

        cmd = """vtysh
        -c "configure terminal"\n"""
        for line in raw_vytsh_cmd.split("\n"):
            cmd += f'''-c "{line}"\n'''
        cmd += '''-c "exit"
        -c "write memory"'''
        # print(cmd)

        exec_result = node_obj.container.exec_run(cmd)
        if exec_result.exit_code != 0:
            raise Exception(
                {
                    "output": exec_result.output.decode("utf-8"),
                    "exit_code": exec_result.exit_code,
                }
            )
        # Get the current config and save it to disk
        config = get_current_config(node_obj.name)["output"]
        save_current_config(config, node_obj.name)
        return {
            "output": exec_result.output.decode("utf-8"),
            "exit_code": exec_result.exit_code,
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))  # noqa: B904
    except docker.errors.NotFound:  # type: ignore
        raise HTTPException(status_code=404, detail="Container not found")  # noqa: B904
    except docker.errors.APIError as e:  # type: ignore
        raise HTTPException(status_code=500, detail="Docker: " + str(e))  # noqa: B904


def copy_syslogs():
    """Copy syslogs from a specific container to the local logs folder, appending only new lines if the file already exists.

    Returns:
        dict: Success message and local file path

    Raises:
        HTTPException: If operation fails
    """
    try:
        # Validate and get the container
        l1_2host = validate_and_get_NodeID("l1-2", "host")
        stream, _ = l1_2host.container.get_archive("/var/log/all_frr_logs.log")

        local_file_path = os.path.join(config.LOGS_DIR, "all_frr_logs.log")

        # Use tarfile to extract the actual file content
        with tarfile.open(fileobj=io.BytesIO(b"".join(stream))) as tar:
            # Get the first file in the tar archive
            member = tar.getmembers()[0]
            with tar.extractfile(member) as extracted_file:
                file_content = extracted_file.read().decode("utf-8", errors="ignore")

        # Write the extracted content to the local file
        with open(local_file_path, "w", encoding="utf-8") as local_file:
            local_file.write(file_content)

        # # Get the number of lines in the existing file if it exists
        # existing_lines = 0
        # if os.path.exists(local_file_path):
        #     with open(local_file_path, encoding="utf-8", errors="ignore") as local_file:
        #         existing_lines = sum(1 for _ in local_file)

        # # Write new content starting from the offset
        # with open(local_file_path, "a", encoding="utf-8") as local_file:
        #     current_lines = 0
        #     buffer = ""  # Buffer to handle incomplete lines
        #     for chunk in stream:
        #         # Decode the chunk to a string
        #         decoded_chunk = chunk.decode("utf-8", errors="ignore")
        #         # Add the chunk to the buffer
        #         buffer += decoded_chunk
        #         # Split the buffer into lines
        #         lines = buffer.splitlines(keepends=True)

        #         # Check if the last line is incomplete
        #         if not lines[-1].endswith("\n"):
        #             buffer = lines.pop()  # Keep the incomplete line in the buffer
        #         else:
        #             buffer = ""  # Clear the buffer if all lines are complete

        #         # Write only new lines that contain valid characters
        #         for line in lines:
        #             current_lines += 1
        #             if current_lines > existing_lines + 1:  # noqa: SIM102
        #                 # Check if the line contains only valid characters
        #                 # Necessary because otherwise the first and last lines contain invalid characters
        #                 if all(c.isprintable() or c == "\n" for c in line):
        #                     local_file.write(line)

        return {
            "message": "File copied successfully",
            "local_file_path": local_file_path,
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error copying syslogs: {str(e)}")  # noqa: B904
    except docker.errors.NotFound:  # type: ignore
        raise HTTPException(status_code=404, detail="Container not found")  # noqa: B904
    except docker.errors.APIError as e:  # type: ignore
        raise HTTPException(status_code=500, detail=f"Docker API error: {str(e)}")  # noqa: B904


def set_bandwidth(request: config.SetBandwidthRequest):
    """Set the bandwidth of a network link.

    Args:
        request: SetBandwidthRequest object with link details

    Returns:
        dict: Command execution results

    Raises:
        HTTPException: If operation fails
    """
    try:
        print("set bandwidth")
        # Validate and get identifiers
        src, dst = validate_and_get_NodeIDs(request.src, request.dst)

        # Get the container object and interface
        interface = get_interface_from_to(src, dst)

        # Check the current link state to preserve existing values
        current_params = check_link_state(src.name, dst.name)
        print(current_params)
        # Command to configure bandwidth while preserving existing values
        cmd = f"""/bin/bash -c '
        tc qdisc del dev {interface} root || true; \
        tc qdisc add dev {interface} root handle 1:0 netem delay {current_params["delay"]} loss {current_params["loss"]} ; \
        tc qdisc add dev {interface} parent 1:1 handle 10: tbf rate {request.bandwidth}mbit burst {current_params["burst"]} latency {current_params["buffer"]}'"""

        # print(cmd)
        # Execute the command in the container
        exec_result = src.container.exec_run(cmd)

        if exec_result.exit_code != 0:
            # TODO: Reset link to default values if the command fails
            raise Exception(
                {
                    "output": exec_result.output.decode("utf-8"),
                    "exit_code": exec_result.exit_code,
                }
            )

        # Return the output of the command
        return {
            "output": exec_result.output.decode("utf-8"),
            "exit_code": exec_result.exit_code,
        }

    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))  # noqa: B904
    except docker.errors.NotFound:  # type: ignore
        raise HTTPException(status_code=404, detail="Container not found")  # noqa: B904
    except docker.errors.APIError as e:  # type: ignore
        raise HTTPException(status_code=500, detail="Docker: " + str(e))  # noqa: B904


def set_buffer(request: config.SetBufferRequest):
    """Set the buffer of a network link.

    Args:
        request: SetBufferRequest object with link details

    Returns:
        dict: Command execution results

    Raises:
        HTTPException: If operation fails
    """
    try:
        # Validate and get identifiers
        src, dst = validate_and_get_NodeIDs(request.src, request.dst)

        # Get the container object and interface
        interface = get_interface_from_to(src, dst)

        # Check the current link state to preserve existing values
        current_params = check_link_state(src.name, dst.name)

        # Command to configure buffer while preserving existing values
        cmd = f"""/bin/bash -c '
        tc qdisc del dev {interface} root || true; \
        tc qdisc add dev {interface} root handle 1:0 netem delay {current_params["delay"]} loss {current_params["loss"]} ; \
        tc qdisc add dev {interface} parent 1:1 handle 10: tbf rate {current_params["bandwidth"]} burst {current_params["burst"]} latency {request.buffer}ms'"""

        # print(cmd)
        # Execute the command in the container
        exec_result = src.container.exec_run(cmd)

        if exec_result.exit_code != 0:
            raise Exception(
                {
                    "output": exec_result.output.decode("utf-8"),
                    "exit_code": exec_result.exit_code,
                }
            )

        # Return the output of the command
        return {
            "output": exec_result.output.decode("utf-8"),
            "exit_code": exec_result.exit_code,
        }

    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))  # noqa: B904
    except docker.errors.NotFound:  # type: ignore
        raise HTTPException(status_code=404, detail="Container not found")  # noqa: B904
    except docker.errors.APIError as e:  # type: ignore
        raise HTTPException(status_code=500, detail="Docker: " + str(e))  # noqa: B904


def set_burst(request: config.SetBurstRequest):
    """Set the burst of a network link.

    Args:
        request: SetBurstRequest object with link details

    Returns:
        dict: Command execution results

    Raises:
        HTTPException: If operation fails
    """
    try:
        # Validate and get identifiers
        src, dst = validate_and_get_NodeIDs(request.src, request.dst)

        # Get the container object and interface
        interface = get_interface_from_to(src, dst)

        # Check the current link state to preserve existing values
        current_params = check_link_state(src.name, dst.name)

        # Command to configure burst while preserving existing values
        cmd = f"""/bin/bash -c '
        tc qdisc del dev {interface} root || true; \
        tc qdisc add dev {interface} root handle 1:0 netem delay {current_params["delay"]} loss {current_params["loss"]} ; \
        tc qdisc add dev {interface} parent 1:1 handle 10: tbf rate {current_params["bandwidth"]} burst {request.burst}b latency {current_params["buffer"]}'"""

        # print(cmd)
        # Execute the command in the container
        exec_result = src.container.exec_run(cmd)

        if exec_result.exit_code != 0:
            raise Exception(
                {
                    "output": exec_result.output.decode("utf-8"),
                    "exit_code": exec_result.exit_code,
                }
            )

        # Return the output of the command
        return {
            "output": exec_result.output.decode("utf-8"),
            "exit_code": exec_result.exit_code,
        }

    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))  # noqa: B904
    except docker.errors.NotFound:  # type: ignore
        raise HTTPException(status_code=404, detail="Container not found")  # noqa: B904
    except docker.errors.APIError as e:  # type: ignore
        raise HTTPException(status_code=500, detail="Docker: " + str(e))  # noqa: B904


def execute(request: config.ExecuteRequest):
    """Execute a command on a router."""
    try:
        node = None
        if request.router:
            # Validate and get container names
            node = validate_and_get_NodeID(request.node, "router")
        else:
            # Validate and get container names
            node = validate_and_get_NodeID(request.node, "host")

        exec_result = node.container.exec_run(request.cmd)

        if exec_result.exit_code != 0:
            raise Exception(
                {
                    "output": exec_result.output.decode("utf-8"),
                    "exit_code": exec_result.exit_code,
                }
            )

        # Return the output of the command
        return {
            "output": exec_result.output.decode("utf-8"),
            "exit_code": exec_result.exit_code,
        }

    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))  # noqa: B904
    except docker.errors.NotFound:  # type: ignore
        raise HTTPException(status_code=404, detail="Container not found")  # noqa: B904
    except docker.errors.APIError as e:  # type: ignore
        raise HTTPException(status_code=500, detail="Docker: " + str(e))  # noqa: B904


def reset_bandwidth(request: config.RemoveChangeRequest):
    """Reset the bandwidth of a network link to its initial value.

    Args:
        request: RemoveChangeRequest object with link details

    Returns:
        dict: Command execution results

    Raises:
        HTTPException: If operation fails
    """
    try:
        # Validate and get identifiers
        src, dst = validate_and_get_NodeIDs(request.src, request.dst)

        # Get the container object and interface
        interface = get_interface_from_to(src, dst)

        # Check the current link state to preserve existing values
        current_params = check_link_state(src.name, dst.name)

        # Get the initial bandwidth value from the configuration
        initial_bandwidth = config.LAB_LINKS[frozenset({src.name, dst.name})][
            "bandwidth"
        ]

        # Command to reset bandwidth while preserving other values
        cmd = f"""/bin/bash -c '
        tc qdisc del dev {interface} root || true; \
        tc qdisc add dev {interface} root handle 1:0 netem delay {current_params["delay"]} loss {current_params["loss"]} ; \
        tc qdisc add dev {interface} parent 1:1 handle 10: tbf rate {initial_bandwidth} burst {current_params["burst"]} latency {current_params["buffer"]}'"""

        # print(cmd)
        # Execute the command in the container
        exec_result = src.container.exec_run(cmd)

        if exec_result.exit_code != 0:
            raise Exception(
                {
                    "output": exec_result.output.decode("utf-8"),
                    "exit_code": exec_result.exit_code,
                }
            )

        # Return the output of the command
        return {
            "output": exec_result.output.decode("utf-8"),
            "exit_code": exec_result.exit_code,
        }

    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))  # noqa: B904
    except docker.errors.NotFound:  # type: ignore
        raise HTTPException(status_code=404, detail="Container not found")  # noqa: B904
    except docker.errors.APIError as e:  # type: ignore
        raise HTTPException(status_code=500, detail="Docker: " + str(e))  # noqa: B904


def reset_burst(request: config.RemoveChangeRequest):
    """Reset the burst of a network link to its initial value.

    Args:
        request: RemoveChangeRequest object with link details

    Returns:
        dict: Command execution results

    Raises:
        HTTPException: If operation fails
    """
    try:
        # Validate and get identifiers
        src, dst = validate_and_get_NodeIDs(request.src, request.dst)

        # Get the container object and interface
        interface = get_interface_from_to(src, dst)

        # Check the current link state to preserve existing values
        current_params = check_link_state(src.name, dst.name)

        # Get the initial burst value from the configuration
        initial_burst = config.LAB_LINKS[frozenset({src.name, dst.name})]["burst"]

        # Command to reset burst while preserving other values
        cmd = f"""/bin/bash -c '
        tc qdisc del dev {interface} root || true; \
        tc qdisc add dev {interface} root handle 1:0 netem delay {current_params["delay"]} loss {current_params["loss"]} ; \
        tc qdisc add dev {interface} parent 1:1 handle 10: tbf rate {current_params["bandwidth"]} burst {initial_burst} latency {current_params["buffer"]}'"""
        # Execute the command in the container
        exec_result = src.container.exec_run(cmd)

        if exec_result.exit_code != 0:
            raise Exception(
                {
                    "output": exec_result.output.decode("utf-8"),
                    "exit_code": exec_result.exit_code,
                }
            )

        # Return the output of the command
        return {
            "output": exec_result.output.decode("utf-8"),
            "exit_code": exec_result.exit_code,
        }

    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))  # noqa: B904
    except docker.errors.NotFound:  # type: ignore
        raise HTTPException(status_code=404, detail="Container not found")  # noqa: B904
    except docker.errors.APIError as e:  # type: ignore
        raise HTTPException(status_code=500, detail="Docker: " + str(e))  # noqa: B904


def reset_buffer(request: config.RemoveChangeRequest):
    """Reset the buffer of a network link to its initial value.

    Args:
        request: RemoveChangeRequest object with link details

    Returns:
        dict: Command execution results

    Raises:
        HTTPException: If operation fails
    """
    try:
        # Validate and get identifiers
        src, dst = validate_and_get_NodeIDs(request.src, request.dst)

        # Get the container object and interface
        interface = get_interface_from_to(src, dst)

        # Check the current link state to preserve existing values
        current_params = check_link_state(src.name, dst.name)

        # Get the initial buffer value from the configuration
        initial_buffer = config.LAB_LINKS[frozenset({src.name, dst.name})]["buffer"]

        # Command to reset buffer while preserving other values
        cmd = f"""/bin/bash -c '
        tc qdisc del dev {interface} root || true; \
        tc qdisc add dev {interface} root handle 1:0 netem delay {current_params["delay"]} loss {current_params["loss"]} ; \
        tc qdisc add dev {interface} parent 1:1 handle 10: tbf rate {current_params["bandwidth"]} burst {current_params["burst"]} latency {initial_buffer}'"""

        # Execute the command in the container
        exec_result = src.container.exec_run(cmd)

        if exec_result.exit_code != 0:
            raise Exception(
                {
                    "output": exec_result.output.decode("utf-8"),
                    "exit_code": exec_result.exit_code,
                }
            )

        # Return the output of the command
        return {
            "output": exec_result.output.decode("utf-8"),
            "exit_code": exec_result.exit_code,
        }

    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))  # noqa: B904
    except docker.errors.NotFound:  # type: ignore
        raise HTTPException(status_code=404, detail="Container not found")  # noqa: B904
    except docker.errors.APIError as e:  # type: ignore
        raise HTTPException(status_code=500, detail="Docker: " + str(e))  # noqa: B904
