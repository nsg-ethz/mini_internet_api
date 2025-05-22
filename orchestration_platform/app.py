import app_logic
import config
import lab_parser
import uvicorn
from fastapi import FastAPI, HTTPException, Query

# Init global variables
config.init_globals()

app = FastAPI()


@app.post("/change_lab")
def post_change_lab(request: config.ChangeLabRequest):
    return app_logic.change_lab(request)


@app.post("/add_loss")
def post_add_loss(request: config.AddLossRequest):
    return app_logic.add_loss(request)


@app.post("/rm_loss")
def post_rm_loss(request: config.RemoveChangeRequest):
    return app_logic.rm_loss(request)


@app.post("/gen_single_flow")
def post_single_flow(request: config.GenFlowRequest):
    return app_logic.single_flow(request)


@app.post("/change_ospf_cost")
def post_change_ospf_weight(request: config.ChangeOSPFCostRequest):
    return app_logic.change_ospf_weight(request)


@app.post("/execute-script-in-container/")
def post_execute_script_in_container(request: config.scriptRequest):
    return app_logic.execute_script_in_container(request)


@app.post("/start_collection")
def post_start_collection():
    return app_logic.start_collection()


@app.post("/stop_collection")
def post_stop_collection():
    return app_logic.stop_collection()


@app.post("/add_delay")
def post_add_delay(request: config.AddDelayRequest):
    return app_logic.add_delay(request)


@app.post("/rm_delay")
def post_rm_delay(request: config.RemoveChangeRequest):
    return app_logic.rm_delay(request)


@app.post("/add_static_route")
def post_add_static_route(request: config.staticRouteRequest):
    return app_logic.add_static_route(request)


@app.post("/rm_static_route")
def post_remove_static_route(request: config.staticRouteRequest):
    return app_logic.rm_static_route(request)


@app.post("/take_snapshot")
def post_take_snapshot():
    return app_logic.take_snapshot()


@app.post("/apply_snapshot")
def post_apply_snapshot(request: config.ApplySnapshotRequest):
    return app_logic.apply_snapshot(request)


@app.post("/disconnect_router")
def post_disconnect_router(request: config.DisconnectContainerRequest):
    return app_logic.disconnect_router(request)


@app.post("/connect_router")
def post_connect_router(request: config.DisconnectContainerRequest):
    return app_logic.connect_router(request)


@app.post("/change_frr_config")
def post_change_frr_config(request: config.ChangeFRRConfigRequest):
    return app_logic.change_FRR_config(request)


@app.post("/copy_syslogs")
def post_copy_syslogs():
    return app_logic.copy_syslogs()


@app.post("/set_bandwidth")
def post_set_bandwidth(request: config.SetBandwidthRequest):
    return app_logic.set_bandwidth(request)


@app.post("/set_buffer")
def post_set_buffer(request: config.SetBufferRequest):
    return app_logic.set_buffer(request)


@app.post("/set_burst")
def post_set_burst(request: config.SetBurstRequest):
    return app_logic.set_burst(request)


@app.post("/execute")
def post_execute(request: config.ExecuteRequest):
    return app_logic.execute(request)


@app.post("/reset_bandwidth")
def post_reset_bandwidth(request: config.RemoveChangeRequest):
    return app_logic.reset_bandwidth(request)


@app.post("/reset_burst")
def post_reset_burst(request: config.RemoveChangeRequest):
    return app_logic.reset_burst(request)


@app.post("/reset_buffer")
def post_reset_buffer(request: config.RemoveChangeRequest):
    return app_logic.reset_buffer(request)


@app.post("/reset_link")
def post_reset_link(request: config.RemoveChangeRequest):
    return app_logic.reset_link(request)



@app.get("/link_state")
def get_check_link_state(src: str, dst: str):
    return app_logic.check_link_state(src, dst)


@app.get("/current_config")
def get_current_config(router: str):
    return app_logic.get_current_config(router)


@app.get("/all_configs")
def get_all_configs():
    return app_logic.get_all_configs()


@app.get("/cmd_status")
def get_status(cmd_id: str):
    return app_logic.get_status(cmd_id)


@app.get("/cmd_output")
def get_output(cmd_id: str):
    return app_logic.get_output(cmd_id)


@app.get("/snmp_param")
def get_snmp_param(host: str, oid: str = ""):
    return app_logic.snmp_param(host, oid)

# These are quite simple and don't have dedicated stubs in app_logic
@app.get("/available_routers")
def get_available_routers():
    return {"routers": config.LAB_NAMES}


@app.get("/router_ips")
def get_router_ips():
    return {"ips": config.IPS}


@app.get("/host_ips")
def get_host_ips():
    return {"ips": app_logic.get_IPS("host")}


@app.get("/links")
def get_links():
    links = [{"src": list(link)[0], "dst": list(link)[1], "details": details} for link, details in config.LAB_LINKS.items()]
    return {"links": links}

@app.get("/events")
def get_events():
    return config.EVENT_DATABASE

# Run the app with Uvicorn
if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=config.PORT)
