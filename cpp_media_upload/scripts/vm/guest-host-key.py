#!/usr/bin/env python3
"""Read a MediaDock guest's Ed25519 public host key through its trusted guest agent."""

import argparse
import base64
import json
import re
import subprocess

VIRSH = ("/usr/bin/virsh", "-c", "qemu:///system")


def agent(domain, command, **arguments):
    request = json.dumps({"execute": command, "arguments": arguments})
    result = subprocess.check_output(
        [*VIRSH, "qemu-agent-command", domain, request, "--timeout", "5"],
        text=True,
    )
    return json.loads(result)["return"]


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("domain", choices=("mediadock-producer", "mediadock-consumer"))
    parser.add_argument("uuid")
    args = parser.parse_args()

    expected = subprocess.check_output([*VIRSH, "domuuid", args.domain], text=True).strip()
    if args.uuid != expected:
        parser.error("domain UUID changed")

    handle = agent(args.uuid, "guest-file-open", path="/etc/ssh/ssh_host_ed25519_key.pub", mode="r")
    try:
        result = agent(args.uuid, "guest-file-read", handle=handle, count=1024)
    finally:
        agent(args.uuid, "guest-file-close", handle=handle)
    key = base64.b64decode(result["buf-b64"], validate=True).decode("ascii")
    fields = key.strip().split(maxsplit=2)
    if len(fields) < 2 or fields[0] != "ssh-ed25519" or not re.fullmatch(r"[A-Za-z0-9+/=]+", fields[1]):
        parser.error("invalid Ed25519 public host key")
    print(" ".join(fields[:2]))


if __name__ == "__main__":
    main()
