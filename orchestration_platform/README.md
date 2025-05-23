# Orchestration Platform for virtual networks

This folder contains a REST API for orchestrating virtual networks. It uses FastAPI and the docker SDK to implement it's endpoints. It must be run on the same machine the virtual network is already running on.
> [!WARNING]  
> This API is inherently insecure as it allows the user to execute arbitrary commands within a docker container and potentially even on the host itself.

## Running the API

### Running in a docker container

#### Setting ports

If a different port on the host should be used: set the `ORCHESTRATION_API_PORT` environment variable to the desired value (eg. `export ORCHESTRATION_API_PORT=7832`).
To change the port within the container set the `PORT` environment variable (eg. `export PORT=8002`)

#### Setting up the container

We provide a simple docker compose script to bring up the API server. If another topology than `demo` is used, change the relevant environment variables in the [docker-compose](docker_compose.yml). The docker socket under `/var/run/docker.sock` must belong to the same groupid (the docker group, see [this](https://docs.docker.com/engine/install/linux-postinstall/)) that is specified in the [Dockerfile](Dockerfile). This is necessary because we're running a Docker-out-of-Docker setup (see [this](https://tdongsi.github.io/blog/2017/04/23/docker-out-of-docker/) for an explanation).

```bash
docker compose up -d
```


### Running on the host (Experimental)

First make sure that all required dependencies are installed like (see [here](app_logic.py) for most imports).
Then the necessary environment variables should be set according to the running network:

    export LABS_DIR=<path-to-the-mini-internet-labs-folder-on-your-machine>
    export LOGS_DIR=<path-to-the-logs-folder-on-your-machine>
    export CURR_LAB=<chosen_lab>
    export LAB_PREFIX=<chosen-AS>

optionally, set the port (the default port is 5432):

    export PORT=8002

So if the mini_internet_api repo is in your home folder and you're using the demo topology:

    export LABS_DIR=~/mini_internet_api/platform/labs/
    export LOGS_DIR=~/mini_internet_api/orchestration_platform/logs/
    export CURR_LAB=demo
    export LAB_PREFIX=55

## Testing the API

The [`test_api.py`](test_api.py) script is a simple way to query the available endpoints.

## Adding endpoints

Adding more/custom endpoints to the code should (hopefully) be reasonably straightforward:

First decide if the endpoint is supposed to be a `GET` or `POST` request. If it doesn't change the internal state of the mini-internet (ie. just fetches some data) it should probably be a `GET` request, otherwise a `POST` request. 
### Adding the route:
If its a `GET` request simply add the route to [app.py](app.py). 
Eg.:
```python
@app.get("/my_endpoint")
def get_my_endpoint(arg1: int, arg2: str):
    return app_logic.my_new_endpoint(arg1, arg2)
```

For a `POST` request first add a pydantic model to [config.py](config.py) like so:
```python
class My_Endpoint_Request(BaseModel):
    arg1: int
    arg2: str
```
Then add the corresponding route to [app.py](app.py).
```python
@app.post("/my_endpoint")
def post_my_endpoint(request: config.My_Endpoint_Request)
    return app_logic.my_endpoint(request)
```
### Adding the request logic
The request logic should be added to an appropiately named function in [app_logic.py](app_logic.py).
The structure of most endpoints tends to be quite similar but other types of requests are also possible and valid.
Usually one wants to have some command executed in a container, perhaps with some arguments from the request.
To do so, you needs to obtain the docker container object of the target. Additionally, you need to assemble a string with the desired command to be executed (special attention should be taken in regard with quotes and escaping characters).
Then execute the command using `container.exec_run(...)`.
Then return the relevant information (eg. if  the command has executed sucessfully? Output of the command?) back to the API client.

## Troubleshooting
In case commands that copy over logs from a container to the host fail due to insufficient permissions, make sure that the group of the [`logs`](logs) folder is set to docker(gid=988).
Setting the permissions can be done with the following command: `chgrp 988 logs`.
