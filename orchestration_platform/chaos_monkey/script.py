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
from abstract_event import AbstractEvent
from undo_event import UndoEvent
from link_lock import Link_Lock
from port_manager import PortManager
from utils import (
    get_random_link,
    get_random_node,
    get_random_nodes,
    get_random_server_and_clients,
    get_server_and_client_IPs,
    get_src_dst_from_link,
    get_event_duration,
)

# Global variables
NODES = ()
LINKS = {}
ROUTER_IPS = {}
HOST_IPS = {}
API_URL = None
INITAL_SNAPSHOT_ID = ""
PORT_MANAGER = PortManager(8000, 8005)
LOGS_DIR = os.path.join(os.path.dirname(__file__), "logs")

# Constants that refer to the events

# Background traffic will have a duration that is uniformly distributed around an avg, this specifies how much longer/shorter the duration can be
BACKGROUND_TRAFFIC_DURATION_SPREAD = 25 
COMPLEX_LOSS_MIN_DURATION = 20
COMPLEX_LOSS_MAX_DURATION = 50
MIN_DELAY = 2  # ms
MAX_DELAY = 300  # ms
MIN_BANDWIDTH = 100 # kbps
MAX_BANDWIDTH = 10000 # kbps

stop_event = threading.Event()

event_queue = queue.PriorityQueue()

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
        response = requests.post(f"{API_URL}/{endpoint}", json=data)
        if response.status_code != 200:
            print(f"{endpoint} Error: {response.status_code} - {response.text}")
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
     # Extend links to also contain the other direction
     # and add locks to the links
    flipped_links = []
    for link in LINKS:
        link["loss_lock"] = Link_Lock()
        link["delay_lock"] = Link_Lock()
        src, dst = get_src_dst_from_link(link)
        newlink = link.copy()
        newlink["src"] = dst
        newlink["dst"] = src
        # The locks on the reverse link need to be different
        newlink["loss_lock"] = Link_Lock()
        newlink["delay_lock"] = Link_Lock()
        flipped_links.append(newlink)

    LINKS.extend(flipped_links)
    # randlink = get_random_link(random.Random(), LINKS)
    # reverse_link = [link for link in LINKS if link["src"] == randlink["dst"] and link["dst"] == randlink["src"]][0]
    # print(f"Random link: {randlink}")
    # print(f"Reverse link: {reverse_link}")
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
    # print(f"Available routers: {NODES}")
    # print(f"Available links: {LINKS}")
    # print(f"Router IPs: {ROUTER_IPS}")
    # print(f"Host IPS: {HOST_IPS}")



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
    cmd = f"flowgrind -q -n {len(client_nodes)}"
    for flow_id, client_ip in enumerate(client_ips):
        cmd += f" -F {flow_id} -J {seed} -H s={server_ip}/{server_ip}:{port},d={client_ip}/{client_ip}:{port} -T s={duration} -G s=q:C:350 -G s=p:L:9055:115.17 -U b=100000"

    return cmd

def get_traffic_duration(rng: random.Random, rate: float):
    return rng.randint(int((1/rate)-BACKGROUND_TRAFFIC_DURATION_SPREAD), int((1/rate)+BACKGROUND_TRAFFIC_DURATION_SPREAD))

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
    cmd = f"flowgrind -q -n {len(client_nodes)}"
    for flow_id, client_ip in enumerate(client_ips):
        cmd += f" -F {flow_id} -J {seed} -H s={server_ip}/{server_ip}:{port},d={client_ip}/{client_ip}:{port} -T s={duration} -G s=q:C:800 -G s=g:N:0.008:0.001"

    return cmd

def gen_videostreaming_traffic(rng: random.Random, rate: float):
    """
    Function to generate a flowgrind command that simulates a webserver serving multiple clients.
    This function can be customized to generate specific traffic patterns.
    """
    server, clients = get_random_server_and_clients(rng, NODES)
    duration = get_traffic_duration(rng, rate)
    print(f"Simulating videostreaming background traffic from {server} to {clients} for {duration} seconds")
    port = PORT_MANAGER.get_port(duration=duration+1)# add 1 second to avoid race conditions.
    if not port:
        print("no port available, continuing")
        return
    cmd = gen_videostreaming_traffic_cmd(server, clients, duration, port, rng.randint(0, 10000))
    print(f"Generated command: {cmd}")
    perform_request("/execute", {"node": server, "router": False, "cmd": cmd, "detach": True})

def gen_webserver_traffic(rng: random.Random, rate: float):
    server, clients = get_random_server_and_clients(rng, NODES)
    duration = get_traffic_duration(rng, rate)
    print(f"Simulating webserver background traffic from {server} to {clients} for {duration} seconds")
    port = PORT_MANAGER.get_port(duration=duration+1)# add 1 second to avoid race conditions.
    if not port:
        print("no port available, continuing")
        return
    cmd = gen_webserver_traffic_cmd(server, clients, duration, port, rng.randint(0, 10000))
    print(f"Generated command: {cmd}")
    perform_request("/execute", {"node": server, "router": False, "cmd": cmd, "detach": True})

def background_traffic(rng: random.Random, rate: float):
    """
    Function to simulate background traffic in the network.
    """
    while not stop_event.is_set():  # Check the stop flag
        # Randomly choose between webserver and videostreaming traffic
        if rng.random() < 0.5:
            gen_webserver_traffic(rng, rate)
        else:
            gen_videostreaming_traffic(rng, rate)

        # Sleep for a random interval before generating the next traffic
        sleeptime = rng.expovariate(rate)
        time.sleep(sleeptime)  # assuming the event duration has an average of 35 seconds

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
        # FIXME: add some way to catch errors of the event and abort the run in case of errors
        # eg by event returning a bool or raising an exception


def elementary_loss(rng: random.Random, link: dict):
    """An event that produces packet loss of multiple consecutive packets, as per the Paper"""
    # TODO: add citation:
    src, dst = get_src_dst_from_link(link)

    link["loss_lock"].acquire_modify()
    # # get current loss rate as the event might overlap with another one
    resp = requests.get(f"{API_URL}/link_state?src={src}&dst={dst}")
    if resp.status_code != 200:
        print(f"Error: {resp.status_code} - {resp.text}")
        link["loss_lock"].release_modify()
        return
    curr_loss = resp.json().get("loss_rate", 0)
    perform_request("add_loss", {"src": src, "dst": dst, "loss_rate": "100"})
    # Probably its fine if we dont wait for a bit since the handling delay should be enough
    perform_request("add_loss", {"src": src, "dst": dst, "loss_rate": curr_loss})
    # perform_request("rm_loss", {"src": src, "dst": dst})
    link["loss_lock"].release_modify()


def complex_loss(rng: random.Random, link: dict):
    """A loss event consisting of multiple elemtary loss events"""
    max_duration = rng.randint(COMPLEX_LOSS_MIN_DURATION, COMPLEX_LOSS_MAX_DURATION)  # seconds
    #  FIXME: maybe log this
    while max_duration > 0:
        elementary_loss(rng, link)
        interval = rng.expovariate(1/5)
        max_duration -= interval
        time.sleep(interval)

def loss_event(args: list):
    # pick out a link
    rng = args[0]
    link = get_random_link(rng, LINKS)
    if(rng.random() < 0.1== 0):
        # in 10% of cases we trigger a complex loss event
        complex_loss(rng, link)
    else:
        elementary_loss(rng, link)


def delay_spike(rng: random.Random, link):
    """Add a simple delay spike that is equally as high(added delay) as it is long
    Eg. a packet that is forwarded over the impacted link usually experiences a propagation delay of 25 ms
    with a delay spike with size 75  it should (currently not implemented) experience a stepwise (due to implementation) decreasing loss with an initial maximum of 100 over a duration of 75ms"""
    delay_size = rng.randint(30, 240) #ms
    # timestamp = time.time_ns()
    src, dst = get_src_dst_from_link(link)
    link["delay_lock"].acquire_modify()
    resp = requests.get(f"{API_URL}/link_state?src={src}&dst={dst}")
    curr_delay = resp.json().get("delay", 0)
    # strip the delay from the units
    try:
        curr_delay = int(curr_delay[:-2])
    except:
        print(f"Error parsing delay: {curr_delay}")
        curr_delay = 5

    perform_request("add_delay", {"src": src, "dst": dst, "delay": delay_size})
    # remaining = timestamp - time.time_ns()
    # FIXME: make this somewhat more rectangular
    # if remaining/1000 > delay_size 
    # time.sleep(remaining/(1000*1000))
    perform_request("add_delay", {"src": src, "dst": dst, "delay": curr_delay})
    link["delay_lock"].release_modify()

def delay_event(args: list):
    rng = args[0]
    link = get_random_link(rng, LINKS)
    delay_spike(rng, link)


def schedule_undo_event(duration: int, action, args: list):
    """
    Function to schedule an undo event
    """
    unroll_time = time.time() + duration
    event = UndoEvent(unroll_time, action, args)
    event_queue.put(event)

def simple_undo(args: list):
    """
    Undo an event by calling the same function with the opposite parameters.
    """
    perform_request(args[0], args[1])

def undo_link_loss_change(args: list):
    """
    Undo a link change by calling the same function with the opposite parameters.
    While making sure that the link is not simultaneously changed by another thread/event
    """
    link  = args[0]
    link["loss_lock"].acquire_modify()
    perform_request(args[1], args[2])
    link["loss_lock"].release_modify()
    link["loss_lock"].release_in_use()

##############################
# Config changes
##############################

class AddBogusStaticRouteEvent(AbstractEvent):
    def __init__(self):
        super().__init__(min_duration=30, max_duration=120)  # Set min and max durations

    def execute(self, rng: random.Random):
        """
        Function to add a valid but wrong static route to a router.
        """
        target, destination, next_hop = get_random_nodes(rng, NODES, 3)
        # Get a random IP from the available IPs
        dest_ip = ROUTER_IPS[destination]
        next_hop_ip = ROUTER_IPS[next_hop]
        # Get a random subnet mask
        subnet_mask = rng.choice(["/16", "/24"])
        # Create the destination IP
        ip_parts = list(map(int, dest_ip.split('.')))
        subnet_bits = int(subnet_mask[1:])
        mask = (0xFFFFFFFF << (32 - subnet_bits)) & 0xFFFFFFFF
        network_ip = [
            (ip_parts[0] & (mask >> 24)) & 0xFF,
            (ip_parts[1] & (mask >> 16)) & 0xFF,
            0,
            0,
        ]
        destination = '.'.join(map(str, network_ip)) + subnet_mask
        perform_request("add_static_route", {"node": target, "destination": destination, "next_hop": next_hop_ip})
        duration = rng.randint(self.min_duration, self.max_duration)
        schedule_undo_event(duration, simple_undo, ["rm_static_route", {"node": target, "destination": destination, "next_hop": next_hop_ip}])

class ChangeOspfWeightEvent(AbstractEvent):
    def __init__(self):
        super().__init__(min_duration=0, max_duration=0)  # No duration, permanent change

    # NOTE: this change will not be undone until the script terminates
    def execute(self, rng: random.Random):
        """
        Function to change the OSPF weight on a random link.
        """
        link = get_random_link(rng, LINKS)
        src, dst = get_src_dst_from_link(link)
        cost = rng.randint(1, 100)
        perform_request("change_ospf_cost", {"src": src, "dst": dst, "cost": cost})

# NOTE: this change will not be undone until the script terminates
class IncreaseDelayEvent(AbstractEvent):
    def __init__(self):
        super().__init__(min_duration=0.5, max_duration=0.5)  # Set min and max durations

    def execute(self, rng: random.Random):
        """
        Function to increase the delay on a random link.
        """
        link = get_random_link(rng, LINKS)
        src, dst = get_src_dst_from_link(link)
        delay = rng.randint(MIN_DELAY, MAX_DELAY)  # ms
        link["delay_lock"].acquire_modify()
        perform_request("add_delay", {"src": src, "dst": dst, "delay": delay})
        link["delay_lock"].release_modify()

class DisconnectRandomLinkEvent(AbstractEvent):
    def __init__(self):
        super().__init__(min_duration=5, max_duration=30)  # Set min and max durations

    def execute(self, rng: random.Random):
        """
        Function to disconnect a random link.
        """
        link = get_random_link(rng, LINKS)
        if link["loss_lock"].acquire_in_use():
            src, dst = get_src_dst_from_link(link)
            link["loss_lock"].acquire_modify()
            resp = requests.get(f"{API_URL}/link_state?src={src}&dst={dst}")
            if resp.status_code != 200:
                print(f"Error: {resp.status_code} - {resp.text}")
                link["loss_lock"].release_modify()
                return
            curr_loss = resp.json().get("loss_rate", 0)
            perform_request("add_loss", {"src": src, "dst": dst, "loss_rate": 100})
            link["loss_lock"].release_modify()
            duration = rng.randint(self.min_duration, self.max_duration)
            schedule_undo_event(duration, undo_link_loss_change, [link, "add_loss", {"src": src, "dst": dst, "loss_rate": curr_loss}])



class DisconnectRandomRouterEvent(AbstractEvent):
    def __init__(self):
        super().__init__(min_duration=60, max_duration=300)  # Set min and max durations

    def execute(self, rng:random.Random):
        """
        Function to disconnect a random node.
        """
        host = get_random_node(rng, NODES)
        perform_request("disconnect_router", {"node": host})
        duration = rng.randint(self.min_duration, self.max_duration)  # seconds
        schedule_undo_event(duration, simple_undo, ["connect_router", {"node": host}])

class MakeLinkLossyEvent(AbstractEvent):
    def __init__(self):
        super().__init__(min_duration=10, max_duration=30)  # Set min and max durations

    def execute(self, rng: random.Random):
        """
        Function to make a random link lossy.
        """
        link = get_random_link(rng, LINKS)
        if link["loss_lock"].acquire_in_use():
            src, dst = get_src_dst_from_link(link)
            link["loss_lock"].acquire_modify()
            # Get current loss rate as the event might overlap with another one
            resp = requests.get(f"{API_URL}/link_state?src={src}&dst={dst}")
            if resp.status_code != 200:
                print(f"Error: {resp.status_code} - {resp.text}")
                link["loss_lock"].release_modify()
                return
            curr_loss = resp.json().get("loss_rate", 0)
            rate = rng.randint(1, 100)
            perform_request("add_loss", {"src": src, "dst": dst, "loss_rate": rate})
            link["loss_lock"].release_modify()
            duration = rng.randint(self.min_duration, self.max_duration)
            schedule_undo_event(duration, undo_link_loss_change, [link, "add_loss", {"src": src, "dst": dst, "loss_rate": curr_loss}])


class ChangeBandwidthEvent(AbstractEvent):
    def __init__(self):
        super().__init__(min_duration=0, max_duration=0)  # Set min and max durations
    
    # NOTE: this change will not be undone until the script terminates
    def execute(self, rng: random.Random):
        """
        Function to change the bandwidth on a random link.
        """
        link = get_random_link(rng, LINKS)
        src, dst = get_src_dst_from_link(link)
        bandwidth = rng.randint(MIN_BANDWIDTH, MAX_BANDWIDTH)  # kbps
        perform_request("set_bandwidth", {"src": src, "dst": dst, "bandwidth": bandwidth})    


def chaos_monkey(rng: random.Random):
    """
    Main function to run the chaos monkey.
    """
    chaos_events = [
        AddBogusStaticRouteEvent(),
        ChangeOspfWeightEvent(),
        IncreaseDelayEvent(),
        DisconnectRandomLinkEvent(),
        DisconnectRandomRouterEvent(),
        MakeLinkLossyEvent(),
        ChangeBandwidthEvent(),
    ]

    # Calculate the average duration for all events
    average_duration = sum(event.get_average_duration() for event in chaos_events) / len(chaos_events)

    # Calculate the rate as the reciprocal of the average duration
    chaos_rate = 1 / average_duration
    while not stop_event.is_set():
        # Randomly choose an event to trigger
        event = rng.choice(chaos_events)
        event.execute(rng)  # Call the event function
        time.sleep(rng.expovariate(chaos_rate))
        




def event_unroller():
    """
    Thread function to unroll events when their time comes.
    """
    while not stop_event.is_set():
        try:
            # Get the next event
            event = event_queue.get(timeout=1)
            now = time.time()
            if event.unroll_time > now:
                # Wait until the event's unroll time, checking regularly if the stop event is set
                while not stop_event.is_set() and time.time() < event.unroll_time:
                    time.sleep(1)
            # Debugging: Check event details
            # print(f"Unrolling event: {event}")
            # print(f"Event args: {event.args}, type: {type(event.args)}")
            # print(f"Event action: {event.action}, callable: {callable(event.action)}")
            
            # Execute the event's action
            arglist = []
            if isinstance(event.args, (list, tuple)):  # Ensure args is iterable
                arglist.extend(event.args)
            else:
                raise TypeError(f"Invalid type for event.args: {type(event.args)}")
            
            event.action(arglist)
        except queue.Empty:
            continue
        except Exception as e:
            print(f"Error in event unroller: {e}")


def reset_config():
    """
    Function to reset the configuration.
    """
    print("Resetting configuration...")
    perform_request("apply_snapshot", {"snapshot_id": INITAL_SNAPSHOT_ID})
    print("Configuration reset complete.")

def reset_links():
    """
    Resets all links to their default values
    """
    for link in LINKS:
        src, dst = get_src_dst_from_link(link)
        print(src)
        perform_request("reset_link", {"src": src, "dst": dst})

def custom_keyboard_interrupt_handler(signal, frame):
    """
    Custom handler for keyboard interrupt (Ctrl+C).
    Resets the configuration and waits for all threads to finish.
    """
    print("\nKeyboard interrupt received. Cleaning up...")
    print("This might take a while...")
    stop_event.set()  # Signal threads to stop
    print("Waiting for threads to finish...")
    for thread in threading.enumerate():
        if thread is not threading.main_thread():  # Skip the main thread
            print(f"Waiting for thread {thread.name} to finish...")
            thread.join(60)  # Wait for the thread to finish
    print("All threads finished.")
    print("Begin unrolling events...")
    # No need to worry about race conditions here as all other threads are dead
    while not event_queue.empty():
        try:
            event = event_queue.get_nowait()  # Get the next event without blocking
            arglist = []
            arglist.extend(event.args) 
            event.action(arglist)  # Execute the event's action
        except Exception as e:
            print(f"Error while unrolling event: {e}")
    print("Resetting config...")
    reset_config()  # Perform cleanup tasks
    reset_links()
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
    parser.add_argument(
        "--loss_rate", type=float, default=1/8, help="Rate of loss events (default: 1/8 events per second)"
    )
    parser.add_argument(
        "--delay_rate", type=float, default=1/8, help="Rate of delay events (default: 1/8 events per second)"
    )
    parser.add_argument(
        "--traffic_rate", type=float, default=1/35, help="Rate and average duration of generated background_traffic (default: 1/35 events per second)"
    )
    args = parser.parse_args()

    # Set the global API_URL
    API_URL = args.api_url

    # Configure the chaos_monkey using the API
    configure()
    rng_loss = random.Random(args.seed)
    rng_delay = random.Random(args.seed)
    rng_traffic = random.Random(args.seed)  # args.traffic_seed
    rng_chaos_monkey = random.Random(args.seed)

    # Start the background traffic in a separate thread
    traffic_thread = threading.Thread(
        target=background_traffic, daemon=True, args=(rng_traffic, args.traffic_rate), name="TrafficGenerator"
    )
    traffic_thread.start()

    # add small loss and delay events all over
    loss_thread = threading.Thread(target = fire_event_exponentially_distributed, args=(rng_loss , args.loss_rate, loss_event, []), name="LossGenerator", daemon=True)
    loss_thread.start()

    delay_thread = threading.Thread(target=fire_event_exponentially_distributed, args=(rng_delay, args.delay_rate, delay_event, []), name="DelayGenerator", daemon=True)
    delay_thread.start()
    # while True:
    #     time.sleep(1)
    event_unroll_thread = threading.Thread(target=event_unroller,args = (), name="EventUnroller", daemon=True)
    event_unroll_thread.start()

    # Continue with other tasks, e.g., chaos monkey
    chaos_monkey(rng_chaos_monkey)
