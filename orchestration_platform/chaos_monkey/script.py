import argparse
import json
import logging
import os
import queue
import random
import signal
import threading
import time
from datetime import datetime

import requests
from port_manager import PortManager
from utils import (
    get_random_link,
    get_random_node,
    get_random_server_and_clients,
    get_server_and_client_IPs,
    get_src_dst_from_link,
)

# Global variables
NODES = ()
LINKS = {}
ROUTER_IPS = {}
HOST_IPS = {}
API_URL = None  # Global variable for the API URL
INITAL_SNAPSHOT_ID = ""
PORT_MANAGER = PortManager(8000, 8005)
LOGS_DIR = os.path.join(os.path.dirname(__file__), "logs")

stop_event = threading.Event()

# Seed randomness for reproducibility
def log_request(endpoint, data, response_status=None, error=None):
    """
    Logs the request details in JSON format, including the thread name.
    """
    log_entry = {
        "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S.%f")[:-3],
        "thread": threading.current_thread().name,  # Add thread name
        "endpoint": endpoint,
        "data": data,
        "response_status": response_status,
        "error": str(error) if error else None,
    }
    logging.info(json.dumps(log_entry))  # Log as a JSON string
    # print(json.dumps(log_entry, indent=4))  # Print for debugging


def perform_request(endpoint, data):
    """
    Wrapper function to perform a request and log the details in JSON format.
    """
    try:
        response = requests.post(f"{API_URL}{endpoint}", json=data)
        log_request(endpoint, data, response_status=response.status_code)
        return response
    except Exception as e:
        log_request(endpoint, data, error=e)
        return None



def configure():
    """
    Fetch and configure global variables using the global API_URL.
    """
    global NODES
    global LINKS
    global ROUTER_IPS
    global HOST_IPS
    global INITAL_SNAPSHOT_ID
    response = requests.get(f"{API_URL}/available_routers")
    NODES = response.json().get("routers", [])
    response = requests.get(f"{API_URL}/links")
    LINKS = response.json().get("links", [])
    response = requests.get(f"{API_URL}/router_ips")
    ROUTER_IPS = response.json().get("ips", [])
    response = requests.get(f"{API_URL}/host_ips")
    HOST_IPS = response.json().get("ips", [])
    for container in [NODES, LINKS, ROUTER_IPS, HOST_IPS]:
        assert len(container) != 0
    response = requests.post(f"{API_URL}/take_snapshot", {})
    INITAL_SNAPSHOT_ID = response.json()["id"]

    # Ensure the logs folder exists
    os.makedirs(LOGS_DIR, exist_ok=True)

    # Configure logging
    logging.basicConfig(
        filename=os.path.join(LOGS_DIR, f"chaos_monkey_{datetime.now().strftime('%Y-%m-%d_%H-%M-%S')}.json"),
        level=logging.INFO,
        format="%(message)s",  # Log only the message (JSON string)
    )
    # for debugging purposes:
    print(f"Available routers: {NODES}")
    print(f"Available links: {LINKS}")
    print(f"Router IPs: {ROUTER_IPS}")
    print(f"Host IPS: {HOST_IPS}")



def gen_webserver_traffic_cmd(
    server_node: str, client_nodes: list, duration: int, port: int, seed: int
):
    """
    Function to generate a flowgrind command that simulates a webserver serving multiple clients.
    This function can be customized to generate specific traffic patterns.
    """
    server_ip, client_ips = get_server_and_client_IPs(server_node, client_nodes, HOST_IPS)

    # For now we dont dump the traffic or store the logfiles somewhere
    # if we want to do this we would need to make corresponding changes in the API
    # What we could do is obtain the flowgrind output and parse it

    # Adapted from the manpages example (https://manpages.ubuntu.com/manpages/xenial/man1/flowgrind.1.html) link to src there(www.3gpp...) is dead however
    cmd = f"flowgrind -n {len(client_nodes)}"
    for flow_id, client_ip in enumerate(client_ips):
        cmd += f" -F {flow_id} -J {seed} -H s={server_ip}/{server_ip}:{port},d={client_ip}/{client_ip}:{port} -T s={duration} -G s=q:C:350 -G s=p:L:9055:115.17 -U b=100000"

    return cmd


def gen_videostreaming_traffic_cmd(
    server_node: str, client_nodes: list, duration: int, port: int, seed: int
):
    """
    Function to generate a flowgrind command that simulates a webserver serving multiple clients.
    This function can be customized to generate specific traffic patterns.
    """
    server_ip, client_ips = get_server_and_client_IPs(server_node, client_nodes, HOST_IPS)

    # For now we dont dump the traffic or store the logfiles somewhere
    # if we want to do this we would need to make corresponding changes in the API
    # What we could do is obtain the flowgrind output and parse it

    # Adapted from the manpages example (https://manpages.ubuntu.com/manpages/xenial/man1/flowgrind.1.html) link to src there(www.3gpp...) is dead however
    cmd = f"flowgrind -n {len(client_nodes)}"
    for flow_id, client_ip in enumerate(client_ips):
        cmd += f" -F {flow_id} -J {seed} -H s={server_ip}/{server_ip}:{port},d={client_ip}/{client_ip}:{port} -T s={duration} -G s=q:C:800 -G s=g:N:0.008:0.001"

    return cmd

def gen_videostreaming_traffic(rng: random.Random):
    """
    Function to generate a flowgrind command that simulates a webserver serving multiple clients.
    This function can be customized to generate specific traffic patterns.
    """
    server, clients = get_random_server_and_clients(rng, NODES)
    duration = rng.randint(10, 60)
    print(f"Simulating videostreaming background traffic from {server} to {clients} for {duration} seconds")
    port = PORT_MANAGER.get_port(duration=duration+1)# add 1 second to avoid race conditions.
    cmd = gen_videostreaming_traffic_cmd(server, clients, duration, port, rng.randint(0, 10000))
    print(f"Generated command: {cmd}")
    perform_request("/execute", {"node": server, "router": False, "cmd": cmd})

def gen_webserver_traffic(rng: random.Random):
    server, clients = get_random_server_and_clients(rng, NODES)
    duration = rng.randint(10, 60)
    print(f"Simulating webserver background traffic from {server} to {clients} for {duration} seconds")
    port = PORT_MANAGER.get_port(duration=duration+1)# add 1 second to avoid race conditions.
    cmd = gen_webserver_traffic_cmd(server, clients, duration, port, rng.randint(0, 10000))
    print(f"Generated command: {cmd}")
    perform_request("/execute", {"node": server, "router": False, "cmd": cmd})

def background_traffic(rng: random.Random):
    """
    Function to simulate background traffic in the network.
    """
    while not stop_event.is_set():  # Check the stop flag
        # Randomly choose between webserver and videostreaming traffic
        if rng.random() < 0.5:
            gen_webserver_traffic(rng)
        else:
            gen_videostreaming_traffic(rng)

        # Sleep for a random interval before generating the next traffic
        time.sleep(rng.expovariate(35))  # assuming the event duration has an average of 35 seconds

def fire_event_exponentially_distributed(
    rng: random.Random, rate: float, event, args: list
):
    """
    Function to fire events at exponentially distributed intervals.
    Args:
        rate (float): The rate parameter (lambda) for the exponential distribution.
                      This is the average number of events per second.
        event: Function to invoke the desired event
        args(list): arguments for the event function, the rng will prepended by convention
    """
    args.insert(0, rng)
    while not stop_event.is_set():
        # Generate the next interval using exponential distribution
        interval = rng.expovariate(rate)
        time.sleep(interval)  # Wait for the interval duration
        event(args)
        # TODO: add some way to catch errors of the event and abort the run in case of errors
        # eg by event returning a bool or raising an exception

# TODO: think about if we want to also do the event in the other direction

def elementary_loss(rng: random.Random, link: dict):
    """An event that produces packet loss of multiple consecutive packets, as per the Paper"""
    # TODO: add citation:
    src, dst = get_src_dst_from_link(link)
    # TODO: think about how to deal with the case where the chaos monkey also has an event on the link
    # Probably a per thread lock that this event obtains during the whole duration and chaos monkey obtains when setting / resetting the event

    # # get current loss rate as the event might overlap with another one
    # resp = requests.get(f"{API_URL}/link_state?src={src}&dst={dst}")
    # curr_loss = resp.json().get("loss_rate", 0)
    perform_request("add_loss", {"src": src, "dst": dst, "loss_rate": "100"})
    # Probably its fine if we dont wait for a bit since the handling delay should be enough
    perform_request("rm_loss", {"src": src, "dst": dst})


def complex_loss(rng: random.Random, link: dict):
    """A loss event consisting of multiple elemtary loss events"""
    max_duration = rng.randint(20, 50)  # seconds
    #  FIXME: maybe log this
    while max_duration > 0:
        elementary_loss(rng, hosts)
        interval = rng.expovariate(5)
        max_duration -= interval
        time.sleep(interval)

def loss_event(args: list):
    # pick out a link
    rng = args[0]
    link = get_random_link(rng, LINKS)
    if(rng.random() % 10 == 0):
        # in 10% of cases we trigger a complex loss event
        complex_loss(rng, link)
    else:
        elementary_loss(rng, link)


def delay_spike(rng: random.Random, link):
    """Add a simple delay spike that is equally as high(added delay) as it is long
    Eg. a packet that is forwarded over the impacted link usually experiences a propagation delay of 25 ms
    with a delay spike with size 75  it will experience a stepwise (due to implementation) decreasing loss with an initial maximum of 100 over a duration of 75ms"""
    delay_size = rng.randint(30, 240) #ms
    # timestamp = time.time_ns()
    src, dst = get_src_dst_from_link(link)
    perform_request("add_delay", {"src": src, "dst": dst, "delay": delay_size})
    # remaining = timestamp - time.time_ns()
    # TODO: make this somewhat more rectangular
    # if remaining/1000 > delay_size 
    # time.sleep(remaining/(1000*1000))
    perform_request("rm_delay", {"src": src, "dst": dst})

def delay_event(args: list):
    rng = args[0]
    link = get_random_link(rng, LINKS)
    delay_spike(rng, link)

class chaos_monkey:
    # place to hold the commands to undo dispatched events(mainly link changes)
    events = ()

# Config changes
def add_bogus_static_route(rng: random.Random):
    perform_request("add_static_route", {"node":"bb2-1", "destination": "23.0.0.0/8", "next_hop":"55.0.30.2"})

def change_ospf_weight(rng: random.Random):
    perform_request("change_ospf_weight", {"node":"bb2-1", "destination": "23.0.0.0/8", "next_hop":"55.0.30.2"})

def increase_delay(rng: random.Random, min_delay: int, max_delay: int):
    """
    Function to increase the delay on a random link.
    """
    link = get_random_link(rng, LINKS)
    src, dst = get_src_dst_from_link(link)
    delay = rng.randint(min_delay, max_delay)  # ms
    perform_request("add_delay", {"src": src, "dst": dst, "delay": delay})

def disconnect_random_link(rng: random.Random):
    """
    Function to disconnect a random link.
    """
    link = get_random_link(rng, LINKS)
    src, dst = get_src_dst_from_link(link)
    perform_request("add_loss", {"src": src, "dst": dst, "loss_rate": "100"})

def disconnect_random_router(rng: random.Random):
    """
    Function to disconnect a random node.
    """
    host = get_random_node(rng, NODES)
    perform_request("disconnect_router", {"node": host})

def make_link_lossy(rng: random.Random):
    """
    Function to make a random link lossy.
    """
    link = get_random_link(rng, LINKS)
    src, dst = get_src_dst_from_link(link)
    rate = rng.randint(0, 100)
    perform_request("add_loss", {"src": src, "dst": dst, "loss_rate": rate})

def reset_config():
    """
    Function to reset the configuration and clean up any ongoing events.
    """
    print("Resetting configuration and cleaning up events...")
    # while not event_queue.empty():
    #     try:
    #         undo_event = event_queue.get_nowait()
    #         perform_request(undo_event["endpoint"], undo_event["data"])
    #     except Exception as e:
    #         print(f"Error while resetting event: {e}")
    print("Configuration reset complete.")

def custom_keyboard_interrupt_handler(signal, frame):
    """
    Custom handler for keyboard interrupt (Ctrl+C).
    Resets the configuration and waits for all threads to finish.
    """
    print("\nKeyboard interrupt received. Cleaning up...")
    stop_event.set()  # Signal threads to stop
    reset_config()  # Perform cleanup tasks
    print("Waiting for threads to finish...")
    for thread in threading.enumerate():
        if thread is not threading.main_thread():  # Skip the main thread
            print(f"Waiting for thread {thread.name} to finish...")
            thread.join(60)  # Wait for the thread to finish
    print("All threads finished.")
    print("Exiting program.")
    exit(0)

# Register the custom keyboard interrupt handler
signal.signal(signal.SIGINT, custom_keyboard_interrupt_handler)

if __name__ == "__main__":
    # Parse command-line arguments
    parser = argparse.ArgumentParser(description="Chaos Monkey Script")
    parser.add_argument(
        "--api-url",
        default="http://localhost:5432",
        help="Base URL for the API (default: http://localhost:5432)",
    )
    parser.add_argument(
        "--seed", type=int, default=42, help="Random seed for reproducibility (default: 42)"
    )
    # If a custom seed is needed for traffic generation
    # parser.add_argument("--traffic_seed", type=int, default=42, help="Random seed for reproducibility of traffic generation")
    args = parser.parse_args()

    # Set the global API_URL
    API_URL = args.api_url

    # Configure the chaos_monkey using the API
    configure()
    rng_loss = random.Random(args.seed)
    rng_delay = random.Random(args.seed)
    rng_traffic = random.Random(args.seed)  # args.traffic_seed

    # Start the background traffic in a separate thread
    traffic_thread = threading.Thread(
        target=background_traffic, daemon=True, args=(rng_traffic,), name="TrafficGenerator"
    )
    traffic_thread.start()

    # add small loss and delay events all over
    loss_thread = threading.Thread(target = fire_event_exponentially_distributed, args=(rng_loss , 8, loss_event, []), name="LossGenerator", daemon=True)
    loss_thread.start()

    delay_thread = threading.Thread(target=fire_event_exponentially_distributed, args=(rng_delay, 8, delay_event, []), name="DelayGenerator", daemon=True)
    delay_thread.start()
    while True:
        time.sleep(1)

    # Continue with other tasks, e.g., chaos monkey
    # chaos_monkey(args.seed)
