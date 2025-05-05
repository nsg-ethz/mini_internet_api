import config
import os
import re


def parse_ASes(filename):
    result = []
    with open(filename) as file:
        for line in file:
            columns = line.strip().split("\t")
            line_data = []
            for entry in columns:
                if entry != "AS" and entry != "Config  ":
                    line_data.append(entry)
            result.append(line_data)
    return result


def parse_routers(filename):
    first_entries = []
    with open(filename) as file:
        for line in file:
            first_entry = line.strip().split()[0]
            first_entries.append(first_entry)
    return first_entries


# Caution: This function is a reimplementation of the bash function in _connect_utils.sh

# If its desired to use the bash function directly this is the equivalent:
# def compute_burstsize_bash(throughput: str, mtu: int = 1500) -> int:
# """
# Call the Bash `compute_burstsize` function from Python.

# Args:
#     throughput (str): Throughput value with units (e.g., "10mbps", "1gbps").
#     mtu (int): Maximum Transmission Unit in bytes (default is 1500).

# Returns:
#     int: Burst size in bits.
# """
# bash_script_path = f"{path_to_repo}/platform/setup/_connect_utils.sh"
# command = f"source {bash_script_path} && compute_burstsize {throughput} {mtu}"

# try:
#     # Run the Bash command and capture the output
#     result = subprocess.run(
#         ["bash", "-c", command],
#         capture_output=True,
#         text=True,
#         check=True
#     )
#     return int(result.stdout.strip())
# except subprocess.CalledProcessError as e:
#     print(f"Error calling Bash function: {e.stderr}")
#     raise


def compute_burstsize(throughput: str, mtu: int = 1500) -> int:
    """
    Compute the burst size as 10% of throughput over a second,
    but at least 10 default MTUs (10 * 1500 bytes).

    Args:
        throughput (str): Throughput value with units (e.g., "10mbps", "1gbps").
        mtu (int): Maximum Transmission Unit in bytes (default is 1500).

    Returns:
        int: Burst size in bits.
    """
    # Minimum burst size in bits (10 * MTU in bits)
    min_burst = 10 * mtu * 8

    # Extract the numeric value and unit from the throughput string
    match = re.match(r"([\d.]+)([a-zA-Z]*)", throughput)
    if not match:
        raise ValueError(f"Invalid throughput format: {throughput}")

    value, unit = match.groups()
    value = float(value)

    # Convert the throughput to bits per second
    unit = unit.lower()
    unit_multipliers = {
        "": 1,
        "bps": 1,
        "kbps": 1_000,
        "mbps": 1_000_000,
        "gbps": 1_000_000_000,
        "tbps": 1_000_000_000_000,
        "kibps": 1024,
        "mibps": 1024**2,
        "gibps": 1024**3,
        "tibps": 1024**4,
    }

    if unit not in unit_multipliers:
        raise ValueError(f"Unsupported unit: {unit}")

    bits_per_second = value * unit_multipliers[unit]

    # Compute 10% of the throughput
    burst = 0.1 * bits_per_second

    # Ensure the burst size is at least the minimum burst size
    return max(int(burst), min_burst)


def parse_links(filename):
    data = []
    with open(filename) as f:
        for line in f:
            if line.strip() and not line.startswith("-"):
                parts = line.strip().split()
                data.append(
                    {
                        "host1": parts[0],
                        "host2": parts[1],
                        "bandwidth": parts[2],
                        "delay": parts[3],
                        "buffer": parts[4],
                        "loss": "0",
                        "burst": str(compute_burstsize(parts[2])),
                    }
                )

    # Build link dictionary
    link_dict = {}
    for entry in data:
        host_pair = frozenset({entry["host1"], entry["host2"]})
        link_dict[host_pair] = {
            "delay": entry["delay"],
            "loss": entry["loss"],
            "bandwidth": entry["bandwidth"],
            "burst": entry["burst"],
            "buffer": entry["buffer"],
        }
    return link_dict


def AS_is_provider(data):
    return data[2] == "empty.txt"


def get_labnames_links(labname, selectedAS):
    filename = f"{config.LABS_DIR}/{labname}/AS_config.txt"
    parsed_data = parse_ASes(filename)
    for data in parsed_data:
        if not AS_is_provider(data):
            print(data)
            if data[0] == selectedAS:
                routers = parse_routers(f"{config.LABS_DIR}/{labname}/{data[1]}")
                links = parse_links(f"{config.LABS_DIR}/{labname}/{data[2]}")
                return routers, links
    # FIXME: Use a custom exception or something that allows the API to nicely return what the issue is
    raise Exception("no such AS")


def get_ips():
    match config.CURR_LAB:
        case "demo":
            return {
                device: f"{config.LAB_PREFIX}.{100 + i + 1}.0.1"
                for i, device in enumerate(config.LAB_NAMES)
            }
        # !FIXME!: THIS IS A WRONG IP CONFIG, IT IS JUST THERE TO BE ABLE TO TEST THE LAB CHANGING
        # also beware: this is not a default case as in a C switch statement, default is just the lab name
        case "default":
            return {
                device: f"{config.LAB_PREFIX}.{100 + i + 1}.0.1"
                for i, device in enumerate(config.LAB_NAMES)
            }
        # If an exact match is not confirmed, this last case will be used
        case _:
            raise NotImplementedError(
                "The requested lab IP function is not yet implemented"
            )


def get_snmp_ips():
    match config.CURR_LAB:
        case "demo":
            return {
                device: f"211.0.{config.LAB_PREFIX}.{2 * i - 1}"
                for i, device in enumerate(config.LAB_NAMES)
            }
        # If an exact match is not confirmed, this last case will be used
        case _:
            raise NotImplementedError(
                "The requested lab IP function is not yet implemented"
            )
