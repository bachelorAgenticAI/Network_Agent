# Network Agent

Autonomous AI agent for network management, diagnosis, remediation, and verification.

The Network Agent analyzes network state, identifies issues based on intent-driven reasoning, and executes corrective actions using structured tool integrations — without manual operational workflows.

## Overview

Network Agent is designed as an **autonomous control-loop system** that:

- Monitors network state continuously
- Collects live network data via tools
- Produces scoped diagnoses
- Generates executable remediation plans
- Applies fixes automatically when required
- Verifies outcomes and summarizes results

The system consists of a LangGraph-based agent workflow and an MCP (Model Context Protocol) server that provides tools for interacting with network devices via RESTCONF and SSH.

## Requirements

- Python `3.13.5`
- Linux
- Network access to configured management endpoints
- `.env` configuration file with API keys (e.g., OpenAI)

## Environment Setup (Linux)

1. Clone the repository and navigate to the project root.

2. Create a virtual environment:
   ```bash
   python3 -m venv .venv
   source .venv/bin/activate
   ```

3. Install dependencies:
   ```bash
   pip install -e .
   ```

4. Copy and configure the environment file:
   ```bash
   cp .env.example .env  # If example exists, otherwise create .env
   # Edit .env to add your OpenAI API key and other required variables
   ```

5. Configure routers in `src/mcp_app/utils/routers.py`:
   - Update the `ROUTERS` dictionary with your actual router details (IP addresses, usernames, passwords).
   - Each router must have RESTCONF enabled to use MCP tools.
   - For ping and traceroute functionality, routers must have SSH enabled.

## Running the System

### Start the MCP Server

The MCP server provides tools for network operations and should load before the agent:

```bash
python3 -m mcp_app.server
```

### Run the Agent

The agent executes the monitoring, diagnosis, remediation, and verification workflow:

```bash
python3 -m agent.agent
```

### Run the simple Agent

Run in src/agent/

Adjust the memory/custom_alerts.json for alert/prompt

```bash
python3 agent-simple.py
```

## Monitoring

The monitoring system runs automatically, providing the input that initiates the agentic workflow. It:

- Collects current network state from all configured devices
- Compares against the previous state to detect changes
- Generates alerts based on predefined thresholds (e.g., error counters, packet drops)
- Supports custom alerts via `src/agent/memory/custom_alerts.json` for specific monitoring scenarios

To set up custom alerts, edit `src/agent/memory/custom_alerts.json` with your desired alert conditions. The system will check these during each monitoring cycle.
