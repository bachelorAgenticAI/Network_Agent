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

## Install dependencies 
- pip install e .

## Run Agent

python3 -m agent.agent

## Run Mcp server

python3 -m mcp_app.server
