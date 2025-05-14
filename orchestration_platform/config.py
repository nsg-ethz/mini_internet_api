import lab_parser
from pydantic import BaseModel, Field
from pydantic_settings import BaseSettings


CURR_LAB = None
LAB_PREFIX = None
LAB_NAMES = ()
LAB_LINKS = ()
IPS = {}
EVENT_DATABASE = {}
SNAPSHOTS = {}
LABS_DIR = None
LOGS_DIR = None
PORT = None
DEFAULT_THROUGHPUT = None
DEFAULT_DELAY = None
DEFAULT_BUFFER = None


class Settings(BaseSettings):
    port: int = 5432
    labs_dir: str = Field(default=...)
    logs_dir: str = Field(default=...)
    curr_lab: str = Field(default=...)
    lab_prefix: str = Field(default=...)


def init_globals():
    global CURR_LAB
    global LAB_PREFIX
    global LAB_NAMES
    global IPS
    global LABS_DIR
    global LOGS_DIR
    global LAB_LINKS
    global PORT
    settings = Settings()
    CURR_LAB = settings.curr_lab
    LAB_PREFIX = settings.lab_prefix
    LABS_DIR = settings.labs_dir
    LOGS_DIR = settings.logs_dir
    PORT = settings.port
    LAB_NAMES, LAB_LINKS = lab_parser.get_labnames_links(CURR_LAB, LAB_PREFIX)
    print(LAB_LINKS)
    # Lazy import to avoid circular dependency
    try:
        from app_logic import get_IPS

        IPS = get_IPS("router")
    except:
        print("Couldn't get IPS from DNS, using default")
        IPS = lab_parser.get_ips()


class ChangeLabRequest(BaseModel):
    lab_name: str
    selected_AS: str


class AddLossRequest(BaseModel):
    src: str
    dst: str
    loss_rate: float


class AddDelayRequest(BaseModel):
    src: str
    dst: str
    delay: float


class RemoveChangeRequest(BaseModel):
    src: str
    dst: str


class GenFlowRequest(BaseModel):
    src: str
    dst: str
    bandwidth: int
    duration: int
    is_tcp: bool = True


class ChangeOSPFCostRequest(BaseModel):
    src: str
    dst: str
    cost: int


class scriptRequest(BaseModel):
    container_name: str
    cmd: str


class staticRouteRequest(BaseModel):
    node: str
    destination: str
    # IP or routername
    next_hop: str


class ApplySnapshotRequest(BaseModel):
    snapshot_id: str


class DisconnectContainerRequest(BaseModel):
    node: str


class ChangeFRRConfigRequest(BaseModel):
    node: str
    cmd: str


class SetBandwidthRequest(BaseModel):
    src: str
    dst: str
    bandwidth: int  # mbit


class SetBufferRequest(BaseModel):
    src: str
    dst: str
    buffer: int  # ms


class SetBurstRequest(BaseModel):
    src: str
    dst: str
    burst: int


class ExecuteRequest(BaseModel):
    node: str
    router: bool
    cmd: str
    detach: bool = False
