import json
import random
import time

import requests

# Define the port
port = 5432
base_url = f"http://localhost:{port}"

RED = "\033[1;31m"
GREEN = "\033[1;32m"
BLUE = "\033[1;34m"
RESET = "\033[0m"

# Define a fixed width for the endpoint string to align the status code
ENDPOINT_WIDTH = 40 # Adjust this value if longer endpoint names appear or if you want more padding

def _print_formatted_response(method: str, endpoint: str, status_code: int, response_json: dict = None, is_error: bool = False):
    """
    Helper function to print formatted responses with aligned status codes.
    """
    prefix = f"{method} {endpoint}"
    # Pad the prefix to the desired width
    padded_prefix = f"{prefix:<{ENDPOINT_WIDTH}}"

    if is_error:
        print(f"{RED}{padded_prefix} code: {status_code}, \n{json.dumps(response_json, indent=2)}{RESET}")
    else:
        print(f"{GREEN}{padded_prefix} code: {status_code}{RESET}")


# Function to send a POST request
def post_request(endpoint, data):
    url = f"{base_url}/{endpoint}"
    headers = {'Content-Type': 'application/json'}
    try:
        response = requests.post(url, headers=headers, data=json.dumps(data))
        if response.status_code not in [200, 204]: # 204 No Content is also a success
            _print_formatted_response("POST", endpoint, response.status_code, response.json(), is_error=True)
        else:
            _print_formatted_response("POST", endpoint, response.status_code, is_error=False)
        return response
    except requests.exceptions.ConnectionError as e:
        _print_formatted_response("POST", endpoint, 500, {'detail': f'Connection Error: {e}'}, is_error=True)
        return type('obj', (object,), {'status_code': 500, 'json': lambda: {'detail': 'Connection Error'}})()


# Function to send a GET request
def get_request(endpoint):
    url = f"{base_url}/{endpoint}"
    try:
        response = requests.get(url)
        if response.status_code != 200:
            _print_formatted_response("GET", endpoint, response.status_code, response.json(), is_error=True)
        else:
            _print_formatted_response("GET", endpoint, response.status_code, is_error=False)
        return response
    except requests.exceptions.ConnectionError as e:
        _print_formatted_response("GET", endpoint, 500, {'detail': f'Connection Error: {e}'}, is_error=True)
        return type('obj', (object,), {'status_code': 500, 'json': lambda: {'detail': 'Connection Error'}})()

print(f"{BLUE}--- Initial Setup ---{RESET}")
response = post_request("take_snapshot",{})
inital_snapshot_id = response.json()["id"] if response.status_code == 200 else "initial_dummy_id"
print(f"Initial snapshot ID: {inital_snapshot_id}")

### START TESTING (Existing tests consolidated for continuity)
print(f"\n{BLUE}--- Existing Test Scenarios ---{RESET}")

for _i in range(1):
    cost = random.randint(10, 130)
    print(f"\n{BLUE}--- Changing OSPF cost to {cost} ---{RESET}")
    response = post_request("change_ospf_cost", {"src": "bb2-1", "dst": "bb2-3", "cost": cost})
    time.sleep(2)


print(f"\n{BLUE}--- Adding Loss and Delay ---{RESET}")
response = post_request("add_loss", {"src": "bb2-1", "dst": "bb2-3", "loss_rate": 5.0})
response = get_request("link_state?src=bb2-1&dst=bb2-3")

response = post_request("add_delay", {"src": "bb2-1", "dst": "bb2-3", "delay": 25.0})
response = get_request("link_state?src=bb2-1&dst=bb2-3")

print(f"\n{BLUE}--- Generating Flows ---{RESET}")
response = post_request("gen_single_flow", {"src": "bb2-1", "dst": "bb2-3", "bandwidth": 50, "duration": 5})
flow_id = response.json().get("ID") if response.status_code == 200 else "flow_dummy_id_1"

response2 = post_request("gen_single_flow", {"src": "bb2-3", "dst": "bb2-1", "bandwidth": 50, "duration": 5})
flow_id2 = response2.json().get("ID") if response2.status_code == 200 else "flow_dummy_id_2"

print(f"\n{BLUE}--- Checking Command Status for Flows ---{RESET}")
for _i in range(3): # Reduced iterations for quick test
    get_request(f"cmd_status?cmd_id={flow_id}")
    get_request(f"cmd_status?cmd_id={flow_id2}")
    time.sleep(0.5)

print(f"\n{BLUE}--- Getting Command Output for Flows ---{RESET}")
get_request(f"cmd_output?cmd_id={flow_id}")
get_request(f"cmd_output?cmd_id={flow_id2}")

print(f"\n{BLUE}--- Removing Loss and Delay ---{RESET}")
response = post_request("rm_loss", {"src": "bb2-1", "dst": "bb2-3"})
response = get_request("link_state?src=bb2-1&dst=bb2-3")

response = post_request("rm_delay", {"src": "bb2-1", "dst": "bb2-3"})
response = get_request("link_state?src=bb2-1&dst=bb2-3")

print(f"\n{BLUE}--- Configuration Endpoints ---{RESET}")
all_configs = get_request("all_configs")
current_config = get_request("current_config?router=bb2-1")

print(f"\n{BLUE}--- Collection Endpoints ---{RESET}")
response = post_request("start_collection", {})
collection_id = response.json().get("ID") if response.status_code == 200 else "collection_dummy_id"
print(f"Collection ID: {collection_id}")

n = 5 # Reduced collection time for quick test
print(f"Collecting for {n} seconds")
for _i in range(n):
    get_request(f"cmd_status?cmd_id={collection_id}")
    time.sleep(1)
post_request("stop_collection", {})

print(f"\n{BLUE}--- SNMP Parameter Endpoint ---{RESET}")
get_request("snmp_param?host=bb2-1&oid=.1.3.6.1.2.1.1")

print(f"\n{BLUE}--- Static Route Management ---{RESET}")
post_request("add_static_route", {"node":"bb2-1", "destination": "23.0.0.0/8", "next_hop":"55.0.30.2"})
post_request("rm_static_route", {"node":"bb2-1", "destination": "23.0.0.0/8", "next_hop":"55.0.30.2"})
post_request("add_static_route", {"node":"bb2-1", "destination": "23.0.0.0/8", "next_hop":"bb2-4"})
post_request("rm_static_route", {"node":"bb2-1", "destination": "23.0.0.0/8", "next_hop":"bb2-4"})

print(f"\n{BLUE}--- Snapshot and Configuration Validation ---{RESET}")
response = get_request("all_configs")
config_before_reset = response.json()["output"] if response.status_code == 200 else {}

response = post_request("take_snapshot",{})
temp_snapshot_id = response.json()["id"] if response.status_code == 200 else "temp_dummy_id"

# Do some config changes
cost = random.randint(10, 130)
post_request("change_ospf_cost", {"src": "bb1-6", "dst": "bb1-8", "cost": cost})
post_request("add_static_route", {"node":"bb2-1", "destination": "23.0.0.0/8", "next_hop":"55.0.30.2"})

# Apply snapshot and cross validate the current config
post_request("apply_snapshot", {"snapshot_id": temp_snapshot_id})
response = get_request("all_configs")
config_after_reset = response.json()["output"] if response.status_code == 200 else {}

print("checking configs to see if snapshot was applied correctly:")
if config_before_reset == config_after_reset:
    print("Successfully applied snapshot!")
else:
    set1 = set(config_before_reset.items())
    set2 = set(config_after_reset.items())
    print(f"{RED}Something went wrong when applying snapshot, diff: {set1-set2}{RESET}")


print(f"\n{BLUE}--- FRR Configuration Change ---{RESET}")
frr_config_cmd = """interface lo
    ip address 1.1.1.1/32
    exit"""
post_request("change_frr_config", {"node": "bb2-1", "cmd": frr_config_cmd})

print(f"\n{BLUE}--- Router Disconnect/Connect ---{RESET}")
post_request("disconnect_router", {"node": "bb2-1"})
input("Press Enter to continue connection test...") # Allows manual observation
post_request("connect_router", {"node": "bb2-1"})

print(f"\n{BLUE}--- Copy Syslogs ---{RESET}")
post_request("copy_syslogs", {})

print(f"\n{BLUE}--- Bandwidth, Buffer, Burst Manipulation ---{RESET}")
src_link_test = "bb1-5"
dst_link_test = "bb1-6"

print("Saving initial link parameters...")
response = get_request(f"link_state?src={src_link_test}&dst={dst_link_test}")
initial_parameters = response.json() if response.status_code == 200 else {}
print(f"Initial parameters: {initial_parameters}")

print("Testing /set_bandwidth...")
post_request("set_bandwidth", {"src": src_link_test, "dst": dst_link_test, "bandwidth": 100})

print("Testing /set_buffer...")
post_request("set_buffer", {"src": src_link_test, "dst": dst_link_test, "buffer": 100})

print("Testing /set_burst...")
post_request("set_burst", {"src": src_link_test, "dst": dst_link_test, "burst": 32000000})

print("Verifying link state after setting parameters...")
get_request(f"link_state?src={src_link_test}&dst={dst_link_test}")

print("Resetting link parameters to default using individual resets...")
post_request("reset_bandwidth", {"src": src_link_test, "dst": dst_link_test})
post_request("reset_buffer", {"src": src_link_test, "dst": dst_link_test})
post_request("reset_burst", {"src": src_link_test, "dst": dst_link_test})

print("Verifying link state after individual resets...")
get_request(f"link_state?src={src_link_test}&dst={dst_link_test}")

print(f"\n{BLUE}--- Testing /reset_link (Full Link Reset) ---{RESET}")
# First, apply some changes to reset
post_request("add_loss", {"src": src_link_test, "dst": dst_link_test, "loss_rate": 2.0})
post_request("add_delay", {"src": src_link_test, "dst": dst_link_test, "delay": 5.0})
post_request("set_bandwidth", {"src": src_link_test, "dst": dst_link_test, "bandwidth": 50})
post_request("set_buffer", {"src": src_link_test, "dst": dst_link_test, "buffer": 50})
post_request("set_burst", {"src": src_link_test, "dst": dst_link_test, "burst": 16000000})
print("Link state before full reset:")
get_request(f"link_state?src={src_link_test}&dst={dst_link_test}")

post_request("reset_link", {"src": src_link_test, "dst": dst_link_test})
print("Link state after full reset:")
get_request(f"link_state?src={src_link_test}&dst={dst_link_test}")


print(f"\n{BLUE}--- Testing /execute Endpoint ---{RESET}")
# Test executing a command on a router
post_request("execute", {"node": "bb2-1", "router": True, "cmd": "vtysh -c 'show ip route'", "detach": False})
# Test executing a command on a host 
post_request("execute", {"node": "bb1-1", "router": False, "cmd": "ping -c 3 8.8.8.8", "detach": True})


print(f"\n{BLUE}--- Testing /change_lab Endpoint ---{RESET}")
post_request("change_lab", {"lab_name": "default", "selected_AS": "2"})
post_request("change_lab", {"lab_name": "demo", "selected_AS": "55"})


print(f"\n{BLUE}--- General Information GET Endpoints ---{RESET}")
get_request("available_routers")
get_request("router_ips")
get_request("host_ips")
get_request("links")
get_request("events")


print(f"\n{BLUE}--- Final Cleanup: Applying Initial Snapshot ---{RESET}")
post_request("apply_snapshot", {"snapshot_id": inital_snapshot_id})
print(f"\n{GREEN}--- All basic tests completed ---{RESET}")