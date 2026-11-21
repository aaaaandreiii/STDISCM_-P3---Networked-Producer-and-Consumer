#!/usr/bin/env python3
"""Render the two MediaDock guests' cloud-init inputs without copying private material."""

import argparse
import json
import re
import subprocess
from pathlib import Path

ROLES = ("producer", "consumer")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("operator")
    parser.add_argument("public_key", type=Path)
    parser.add_argument("output_dir", type=Path)
    args = parser.parse_args()

    if not re.fullmatch(r"[a-z_][a-z0-9_-]{0,30}", args.operator) or args.operator in {
        "root", "ubuntu", "daemon", "nobody"
    }:
        parser.error("select a dedicated, unprivileged Linux username")

    key = args.public_key.read_text(encoding="utf-8").splitlines()
    if len(key) != 1:
        parser.error("provide one SSH Ed25519 public key")
    fields = key[0].split(maxsplit=2)
    if len(fields) < 2 or fields[0] != "ssh-ed25519":
        parser.error("provide an SSH Ed25519 public key")
    if subprocess.run(["ssh-keygen", "-lf", str(args.public_key)],
                      stdout=subprocess.DEVNULL, check=False).returncode:
        parser.error("invalid SSH public key")

    setup = Path(__file__).with_name("setup-guest.sh").read_text(encoding="utf-8")
    if not args.output_dir.is_dir():
        parser.error("output dir must already exist")
    for role in ROLES:
        name = f"mediadock-{role}"
        config = {
            "hostname": name,
            "ssh_pwauth": False,
            "disable_root": True,
            "users": [{
                "name": args.operator,
                "shell": "/bin/bash",
                "lock_passwd": True,
                "ssh_authorized_keys": [" ".join(fields[:2])],
            }],
            "write_files": [{
                "path": "/usr/local/sbin/mediadock-setup-guest",
                "permissions": "0700",
                "content": setup,
            }],
            "runcmd": [["/usr/local/sbin/mediadock-setup-guest", args.operator, role]],
        }
        for suffix, content in (
            ("user-data", "#cloud-config\n" + json.dumps(config, indent=2) + "\n"),
            ("meta-data", f"instance-id: {name}\nlocal-hostname: {name}\n"),
        ):
            with (args.output_dir / f"{name}.{suffix}").open("x", encoding="utf-8") as output:
                output.write(content)


if __name__ == "__main__":
    main()
