import json
import random
import time

import requests

# Define the port
port = 5432
base_url = f"http://localhost:{port}"

RED = "\033[1;31m"
GREEN = "\033[1;32m"
RESET = "\033[0m"


# Function to send a POST request
def post_request(endpoint, data):
    url = f"{base_url}/{endpoint}"
    headers = {'Content-Type': 'application/json'}
    response = requests.post(url, headers=headers, data=json.dumps(data))
    if response.status_code != 200:
        print(f"{RED}{endpoint}           code: {response.status_code}, \n{response.json()}{RESET}")
    else:
        # Omit data when command was successful
        print(f"{GREEN}{endpoint}           code: {response.status_code}\n{RESET}")
    return response

# Function to send a GET request
def get_request(endpoint):
    url = f"{base_url}/{endpoint}"
    response = requests.get(url)
    if response.status_code != 200:
        print(f"{RED}{endpoint}           code: {response.status_code}, \n{response.json()}{RESET}")
    else:
        # Omit data when command was successful
        print(f"{GREEN}{endpoint}           code: {response.status_code}\n{RESET}")
    return response

test_old = True

response = post_request("take_snapshot",{})
inital_snapshot_id = response.json()["id"]

### START TESTING
if test_old:

    for _i in range(1):
        cost = random.randint(10, 130)
        # Change OSPF cost
        response = post_request("change_ospf_cost", {"src": "bb2-1", "dst": "bb2-3", "cost": str(cost)})
        # print(response)
        time.sleep(2)


    # Add loss
    response = post_request("add_loss", {"src": "bb2-1", "dst": "bb2-3", "loss_rate": "5"})
    # print(response.json())

    response = get_request("link_state?src=bb2-1&dst=bb2-3")
    # print(response.json())

    # Add delay
    response = post_request("add_delay", {"src": "bb2-1", "dst": "bb2-3", "delay": "25"})
    # print(response.json())

    # Generate single flow (src -> dst)
    response = post_request("gen_single_flow", {"src": "bb2-1", "dst": "bb2-3", "bandwidth": "50", "duration": "5"})
    # print(response.json())
    flow_id = response.json().get("ID")

    # Generate single flow (dst -> src)
    response2 = post_request("gen_single_flow", {"src": "bb2-3", "dst": "bb2-1", "bandwidth": "50", "duration": "5"})
    # print(response2.json())
    flow_id2 = response2.json().get("ID")

    # Check command status for 15 iterations
    for _i in range(15):
        status1 = get_request(f"cmd_status?cmd_id={flow_id}")
        # print(status1.json())
        status2 = get_request(f"cmd_status?cmd_id={flow_id2}")
        # print(status2.json())
        time.sleep(0.5)

    # Get command output
    output1 = get_request(f"cmd_output?cmd_id={flow_id}")
    # print(output1.json())
    output2 = get_request(f"cmd_output?cmd_id={flow_id2}")
    # print(output2.json())

    response = get_request("link_state?src=bb2-1&dst=bb2-3")

    # Remove loss and delay, show values in between to check that only one thing is removed at a time
    response = post_request("rm_loss", {"src": "bb2-1", "dst": "bb2-3"})

    response = get_request("link_state?src=bb2-1&dst=bb2-3")

    response = post_request("rm_delay", {"src": "bb2-1", "dst": "bb2-3"})

    response = get_request("link_state?src=bb2-1&dst=bb2-3")

    # Get all configurations
    all_configs = get_request("all_configs")
    # print(all_configs.json())

    # Get current configuration for a specific router
    current_config = get_request("current_config?router=bb2-1")
    # print(current_config.json())

    response = post_request("start_collection", {})
    collection_id = response.json().get("ID")
    # print(response.json())

    n = 10
    print(f"collecting for {n} seconds")
    for _i in range(n):
        status1 = get_request(f"cmd_status?cmd_id={collection_id}")
        # print(status1.json())
        time.sleep(1)
    response = post_request("stop_collection", {})
    # print(response.json())

    response = get_request("snmp_param?host=bb2-1&oid=.1.3.6.1.2.1.1")
    # print(response.json())

    response = post_request("add_static_route", {"node":"bb2-1", "destination": "23.0.0.0/8", "next_hop":"55.0.30.2"})

    response = post_request("rm_static_route", {"node":"bb2-1", "destination": "23.0.0.0/8", "next_hop":"55.0.30.2"})

    response = post_request("add_static_route", {"node":"bb2-1", "destination": "23.0.0.0/8", "next_hop":"bb2-4"})

    response = post_request("rm_static_route", {"node":"bb2-1", "destination": "23.0.0.0/8", "next_hop":"bb2-4"})

    response = get_request("all_configs")
    config_before_reset = response.json()["output"]

    response = post_request("take_snapshot",{})
    id = response.json()["id"]

    # Do some config changes

    # Change OSPF cost
    cost = random.randint(10, 130)
    response = post_request("change_ospf_cost", {"src": "bb1-6", "dst": "bb2-3", "cost": str(cost)})
    # add static route
    response = post_request("add_static_route", {"node":"bb2-1", "destination": "23.0.0.0/8", "next_hop":"55.0.30.2"})

    # Apply snapshot and cross validate the current config
    post_request("apply_snapshot", {"snapshot_id": id})
    response = get_request("all_configs")
    config_after_reset = response.json()["output"]

    print("checking configs to see if snapshot was applied correctly:")
    if (config_after_reset != config_before_reset):
        set1 = set(config_before_reset.items())
        set2 = set(config_after_reset.items())
        print("something went wrong when applying snapshot, diff:")
        print(set1-set2)
    else:
        print("Successfully applied snapshot!")
    # Test /change_frr_config
        print("Testing /change_frr_config...")
        frr_config_cmd = """interface lo
            ip address 1.1.1.1/32
            exit"""
        response = post_request("change_frr_config", {"node": "bb2-1", "cmd": frr_config_cmd})
        print(response.json())

    # Test /disconnect_router
    print("Testing /disconnect_router...")
    response = post_request("disconnect_router", {"node": "bb2-1"})
    print(response.json())

    input("Press Enter to continue...")
    # Test /resume_router
    print("Testing /connect_router...")
    response = post_request("connect_router", {"node": "bb2-1"})
    print(response.json())

    response = post_request("rm_delay", {"src": "bb2-1", "dst": "bb2-3"})

    print(response.json())

    # Test /copy_file
    print("Testing /copy_syslogs...")
    response = post_request("copy_syslogs", {})
    print(response.json())




# Test /set_bandwidth, /set_buffer, and /set_burst endpoints
print("Testing /set_bandwidth, /set_buffer, and /set_burst endpoints...")

# Define test parameters
src = "bb1-5"
dst = "bb1-6"

# Step 1: Save initial parameters
print("Saving initial link parameters...")
response = get_request(f"link_state?src={src}&dst={dst}")
if response.status_code == 200:
    initial_parameters = response.json()
    print(f"Initial parameters: {initial_parameters}")
else:
    print("Failed to retrieve initial parameters. Exiting...")
    exit(1)

# Step 2: Test /set_bandwidth
print("Testing /set_bandwidth...")
bandwidth_request = {"src": src, "dst": dst, "bandwidth": "100"}
response = post_request("set_bandwidth", bandwidth_request)
print(response.json())

# Step 3: Test /set_buffer
print("Testing /set_buffer...")
buffer_request = {"src": src, "dst": dst, "buffer": "100"}
response = post_request("set_buffer", buffer_request)
print(response.json())

# Step 4: Test /set_burst
print("Testing /set_burst...")
burst_request = {"src": src, "dst": dst, "burst": "32000000"}
response = post_request("set_burst", burst_request)
print(response.json())

# Step 5: Verify the link state after setting parameters
print("Verifying link state after setting parameters...")
response = get_request(f"link_state?src={src}&dst={dst}")
print(response.json())

# Step 6: Reset link parameters to default
print("Resetting link parameters to default...")
response = post_request("rm_loss", {"src": src, "dst": dst})
print(response.json())
response = post_request("rm_delay", {"src": src, "dst": dst})
print(response.json())

# Step 7: Verify the link state after resetting parameters
print("Verifying link state after resetting parameters...")
response = get_request(f"link_state?src={src}&dst={dst}")
print(response.json())

# Step 8: Restore initial parameters
print("Restoring initial link parameters...")
response = post_request("reset_bandwidth", {"src": src, "dst": dst})
print(response.json())
response = post_request("reset_buffer", {"src": src, "dst": dst})
print(response.json())
response = post_request("reset_burst", {"src": src, "dst": dst})
print(response.json())

# Step 9: Verify the restored parameters
print("Verifying restored link parameters...")
response = get_request(f"link_state?src={src}&dst={dst}")
print(response.json())

post_request("apply_snapshot", {"snapshot_id": inital_snapshot_id})
