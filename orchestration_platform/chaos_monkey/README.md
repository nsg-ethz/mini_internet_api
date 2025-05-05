# Chaos Monkey Script

## Overview
The `script.py` is designed to simulate failures in a controlled environment to test the resilience of virtual networks managed by the orchestration platform. 

## Features
- Randomized failure injection.
- Logging of all disruptions for analysis.
- Safe execution with rollback mechanisms.

## Design
During initialization the script will self-configure using the orchestration platform API.
Then multiple threads will get started:
1. Handles background traffic generation, emulating webserver traffic and videostreaming traffic
2. Handles creation of realistic small(simple) loss events and more complex losses on links.
3. Handles creation of realistic small(simple) delay events.
The main thread will then transition into "chaos monkey mode" where it will randomly perform some of the following actions:
- Disconnect a router
- bring down a link
- change a links bandwidth
- add a static route
- change ospf weight

## Usage
```
python3 script.py [-h] [--api-url API_URL] [--seed SEED]

Chaos Monkey Script

options:
  -h, --help         show this help message and exit
  --api-url API_URL  Base URL for the API (default: http://localhost:5432)
  --seed SEED        Random seed for reproducibility (default: 42)
```
3. Review the logs in the `logs/` directory.
