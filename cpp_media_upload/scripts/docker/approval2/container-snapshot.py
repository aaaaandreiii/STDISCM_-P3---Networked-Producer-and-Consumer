"""Emit only the Docker state fields needed by the image gate."""

import json
import sys


def container_state(container):
    state = container["State"]
    status = state["Status"]
    health = state.get("Health")
    if health is None:
        config = container.get("Config") or {}
        check = (config.get("Healthcheck") or {}).get("Test")
        health_status = "unreported" if check and check != ["NONE"] else "no-healthcheck"
    else:
        health_status = health["Status"]
        if health_status not in {"starting", "healthy", "unhealthy"}:
            raise ValueError("unrecognized health status")

    running = state["Running"]
    started_at = state["StartedAt"]
    restarts = container["RestartCount"]
    if not isinstance(status, str) or not isinstance(running, bool):
        raise ValueError("invalid container state")
    if not isinstance(started_at, str) or type(restarts) is not int or restarts < 0:
        raise ValueError("invalid lifecycle fields")

    if status == "running" and running:
        classification = f"running-{health_status}"
    elif status in {"created", "exited", "dead"} and not running:
        classification = "stopped"
    elif status in {"paused", "restarting", "removing"}:
        classification = status
    else:
        raise ValueError("unrecognized or inconsistent container state")

    return {
        "id": container["Id"],
        "state": status,
        "running": running,
        "started_at": started_at,
        "restart_count": restarts,
        "health": health_status,
        "classification": classification,
    }


def main(expected_ids):
    try:
        containers = json.load(sys.stdin)
        if not isinstance(containers, list) or len(containers) != len(expected_ids):
            raise ValueError("unexpected number of inspected containers")
        states = [container_state(container) for container in containers]
        by_id = {state["id"]: state for state in states}
        if len(by_id) != len(states) or set(by_id) != set(expected_ids):
            raise ValueError("inspected container IDs do not match the baseline")
        for container_id in sorted(by_id):
            print(json.dumps(by_id[container_id], sort_keys=True))
    except (KeyError, TypeError, ValueError, AttributeError):
        # Raw Docker inspect data can contain environment variables and credentials.
        print("Docker container snapshot rejected incomplete or unexpected inspection data.", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
