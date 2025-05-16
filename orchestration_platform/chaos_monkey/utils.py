import random


def get_random_server_and_clients(rng: random.Random, nodes: list, num_clients: int = 6):
    """
    Function to get a random server and clients from the list of nodes.
    """
    if num_clients > len(nodes):
        raise ValueError("Number of clients exceeds available nodes")
    if num_clients < 2:
        raise ValueError("Number of clients must be at least 2")
    num_clients = rng.randint(2, num_clients)
    sampled_nodes = rng.sample(nodes, k=num_clients)
    server = sampled_nodes[0]
    clients = sampled_nodes[1:]
    return server, clients


def get_random_link(rng: random.Random, links: dict):
    """
    Get a random link from the available ones.
    """
    return rng.choice(links)


def get_random_node(rng: random.Random, nodes: list):
    """
    Get a random node from the list of nodes.
    """
    return rng.choice(nodes)

def get_random_nodes(rng: random.Random, nodes: list, num_nodes: int):
    """
    Get a random number of nodes from the list of nodes.
    """
    if num_nodes > len(nodes):
        raise ValueError("Number of nodes exceeds available nodes")
    return rng.sample(nodes, k=num_nodes)


def get_server_and_client_IPs(server_node: str, client_nodes: list, ips: dict):
    """
    Get the server and client IPs based on the node type.
    """
    server_ip = ips[server_node]
    client_ips = [ips[node] for node in client_nodes]
    return server_ip, client_ips


def get_src_dst_from_link(link: dict):
    """
    Get the source and destination from a link dictionary.
    """
    return (link["src"], link["dst"])


def get_event_duration(rng: random.Random, min_duration, max_duration):
    """
    Function to get a random event duration.
    """
    return rng.randint(min_duration, max_duration)  # seconds