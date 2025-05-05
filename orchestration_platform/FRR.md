# Some notes about FRR
These are some semi organized notes on things I have found during my semester thesis. 

## FRR API to make small changes easily?
Currently my orchestration API requires a long chain of vtysh commands to change some configuration.
We wanted to explore if there is a simpler way to interact with FRR.

There is the FRR Northbound API([Documentation](https://docs.frrouting.org/projects/dev-guide/en/latest/northbound/northbound.html)), it needs to be compiled into FRR, not sure if thats the case by default. As far as I understand, it is part of a general push to make FRR "an API-first routing stack".

It provides currently provides a gRPC interface to talk to FRR : 

### Example (courtesy of deepseek :)):

### Prerequisites

    FRR Installed with Northbound API:

        Ensure FRR is installed and configured with the Northbound API enabled.

        Refer to the FRR documentation for installation instructions.

    Python gRPC Libraries:

        Install the required Python libraries for gRPC:
        bash
        Copy

        pip install grpcio grpcio-tools

    FRR Northbound API .proto Files:

        Obtain the .proto files for the FRR Northbound API. These are typically available in the FRR source code repository (e.g., frr/proto/frr-northbound.proto).

### Steps to Use the gRPC Interface from Python
1. Generate Python gRPC Code

    Use the protoc compiler to generate Python gRPC code from the .proto file.

    Example:
    bash
    Copy

    python -m grpc_tools.protoc -I<path_to_proto_files> --python_out=. --grpc_python_out=. frr_northbound.proto

    This will generate two files:

        frr_northbound_pb2.py: Contains the message definitions.

        frr_northbound_pb2_grpc.py: Contains the gRPC service definitions.

2. Write a Python Client

    Use the generated Python files to write a client that interacts with the FRR Northbound API.

    Example: Changing OSPF Weight and Adding a Static Route

    Below is an example Python script that demonstrates how to:

        Change the OSPF weight for a specific interface.

        Add a static route.

    ```python
    import grpc
    import frr_northbound_pb2
    import frr_northbound_pb2_grpc

    # Connect to the FRR Northbound API gRPC server
    channel = grpc.insecure_channel('localhost:1234')  # Replace with your FRR gRPC server address
    stub = frr_northbound_pb2_grpc.NorthboundStub(channel)

    # Example 1: Change OSPF Weight for an Interface
    def set_ospf_weight(interface_name, weight):
        # Create a configuration request
        config_request = frr_northbound_pb2.SetConfigRequest()
        
        # Specify the OSPF configuration
        ospf_config = config_request.config.ospf
        interface_config = ospf_config.interfaces.add()
        interface_config.name = interface_name
        interface_config.cost = weight  # Set the OSPF weight (cost)

        # Send the request to FRR
        response = stub.SetConfig(config_request)
        print("OSPF Weight Set Response:", response)

    # Example 2: Add a Static Route
    def add_static_route(destination, next_hop):
        # Create a configuration request
        config_request = frr_northbound_pb2.SetConfigRequest()
        
        # Specify the static route configuration
        static_route = config_request.config.static_routes.add()
        static_route.destination = destination  # e.g., "192.168.1.0/24"
        static_route.next_hop = next_hop  # e.g., "10.0.0.1"

        # Send the request to FRR
        response = stub.SetConfig(config_request)
        print("Static Route Added Response:", response)

    # Run the examples
    if __name__ == "__main__":
        # Change OSPF weight for interface "eth0" to 10
        set_ospf_weight("eth0", 10)

        # Add a static route for "192.168.1.0/24" with next-hop "10.0.0.1"
        add_static_route("192.168.1.0/24", "10.0.0.1")

    ```

### Why I didn't use it
Acessinh the API would require either port forwarding and a direct connection to the container or the scipt being executed directly in the router container. 
Although the configuration changes are a bit more straightforward, these additional drawbacks combined with the fact that I already had the usual implementation working, made me decide against doing this.

## FRR config files

FRR is somewhat special in the way it deals with its config files. The default config file under `/etc/frr/frr.conf` contains some lines that are supposed to make it more easily human readable:
```
"Building configuration...",
"Current configuration:",
"!",
"end",
```
FRR also provides a way to load a configuration from a file, on some versions there is a `load` command in the configuration terminal. Otherwise there is a python script available under `/usr/lib/frr/frr-reload.py`(usage:`/usr/lib/frr/frr-reload.py --reload my_new_config.conf`). 
Unfortunately however, these ways to load a configuration file only support "pure" configuration files that don't contain any of the aforementioned lines and characters, ie. they just consist of valid vtysh configuration commands.


 