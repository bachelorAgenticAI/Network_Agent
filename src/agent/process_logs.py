import json
from collections import defaultdict
from datetime import datetime


def parse_timestamp(ts_str):
    return datetime.fromisoformat(ts_str.replace("Z", "+00:00"))


def process_logs(file_path):
    logs = []
    with open(file_path) as f:
        for line in f:
            logs.append(json.loads(line.strip()))

    # Categorize by node
    categorized = defaultdict(list)
    for log in logs:
        categorized[log["node"]].append(log)

    # Find durations for phases
    phases = ["intent", "diagnose", "remediation"]
    durations = {}

    for phase in phases:
        phase_logs = categorized[phase]
        starts = [log for log in phase_logs if log["direction"] == "in"]
        ends = [log for log in phase_logs if log["direction"] == "out"]

        # Assuming starts and ends are paired in order
        phase_durations = []
        for start, end in zip(starts, ends, strict=False):
            start_time = parse_timestamp(start["ts"])
            end_time = parse_timestamp(end["ts"])
            duration = (end_time - start_time).total_seconds()
            phase_durations.append(
                {"start": start["ts"], "end": end["ts"], "duration_seconds": duration}
            )
        durations[phase] = phase_durations

    # Calculate total process duration
    all_timestamps = [parse_timestamp(log["ts"]) for log in logs]
    if all_timestamps:
        start_time = min(all_timestamps)
        end_time = max(all_timestamps)
        total_duration = (end_time - start_time).total_seconds()
        durations["total_process"] = {
            "start": start_time.isoformat(),
            "end": end_time.isoformat(),
            "duration_seconds": total_duration,
        }

    # Calculate cycles per node (number of 'in' directions)
    node_cycles = {}
    for node, logs in categorized.items():
        cycles = len([log for log in logs if log["direction"] == "in"])
        node_cycles[node] = cycles

    durations["node_cycles"] = node_cycles

    # Calculate additional metrics
    total_cycles = sum(node_cycles.values())
    total_tries = node_cycles.get("intent", 0)  # Assuming intent calls represent tries
    
    # Check success/fail from assess_verify
    success = False
    if "assess_verify" in categorized:
        assess_logs = categorized["assess_verify"]
        out_logs = [log for log in assess_logs if log["direction"] == "out"]
        if out_logs:
            last_out = out_logs[-1]
            data = last_out.get("data", {})
            verify = data.get("verify", {})
            success = verify.get("passed", False)
    
    success_rate = 1.0 if success else 0.0  # For single incident, 1 or 0
    
    durations["summary"] = {
        "total_time_seconds": durations["total_process"]["duration_seconds"],
        "total_cycles": total_cycles,
        "total_tries": total_tries,
        "success_rate": success_rate
    }

    return categorized, durations


if __name__ == "__main__":
    categorized, durations = process_logs("/home/memcache/alpha/src/agent/logger/node_io_log.jsonl")

    # Write durations
    with open("/home/memcache/alpha/src/agent/logger/durations.json", "w") as f:
        json.dump(durations, f, indent=2)
