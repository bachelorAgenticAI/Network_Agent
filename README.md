# Network Agent

Autonomous AI agent for network management, diagnosis, and remediation.

The Network Agent analyzes network state, identifies issues based on intent-driven reasoning, and executes corrective actions using structured tool integrations — without manual operational workflows.

---

## Overview

Network Agent is designed as an **autonomous control-loop system** that:

- Interprets operator intent
- Collects live network data via tools
- Produces scoped diagnoses
- Generates executable remediation plans
- Applies fixes automatically when required
- Verifies outcomes and summarizes results

---

## Requirements

- Python `>=3.11,<3.14`
- Linux or Windows
- Network access to configured management endpoints
- `.env` configuration file

---

## Environment Setup

Copy the example environment file and configure required variables:

```bash
cp .env.example .env
```

Edit .env and provide the necessary configuration values.

---

## Installation

All commands are executed from the project root directory.

1. Create Virtual Environment
### Windows (PowerShell)
```
python -m venv .venv
.venv\Scripts\Activate.ps1
```
### Linux / macOS
```
python3 -m venv .venv
source .venv/bin/activate
```
## 2. Install Dependencies
```
pip install .
```
This installs the project and all required dependencies.

---

## Running the Agent

Start the interactive agent:
```
python3 src/agent/agent.py
```
Start the MCP server:
```
python3 src/mc/server.py
```
