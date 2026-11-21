#!/usr/bin/env bash
set -euo pipefail

cd "$(dirname "$0")/../.."
if docker compose version >/dev/null 2>&1; then
  compose=(docker compose)
else
  compose=(docker-compose)
fi

work_dir=$(mktemp -d)
trap 'rm -f "$work_dir"/{build,consumer,normal,producer}.json; rmdir "$work_dir"' EXIT

revision=0123456789abcdef0123456789abcdef01234567
config() {
  env -i PATH="$PATH" HOME="$HOME" IMAGE_REVISION="$revision" CONSUMER_PRIVATE_IP=127.0.0.1 \
    "${compose[@]}" --env-file .env.demo.example "$@" config --format json
}
config -f infra/build.compose.yml > "$work_dir/build.json"
config -f infra/consumer.compose.yml > "$work_dir/normal.json"
config -f infra/consumer.compose.yml --profile overload > "$work_dir/consumer.json"
config -f infra/producer.compose.yml > "$work_dir/producer.json"

python3 - "$work_dir" "$revision" <<'PY'
import json
from pathlib import Path
import sys

work_dir, revision = Path(sys.argv[1]), sys.argv[2]

def config(name):
    return json.loads((work_dir / f"{name}.json").read_text())

def args(service):
    command = service["command"]
    return dict(zip(command[::2], command[1::2]))

def ports(service):
    return {(entry["host_ip"], int(entry["published"]), entry["target"]) for entry in service["ports"]}

def prebuilt(service, role):
    assert service["image"] == f"mediadock/{role}:{revision}"
    assert service["pull_policy"] == "never"
    assert "build" not in service

build = config("build")["services"]
assert set(build) == {"consumer", "producer"}
for role, service in build.items():
    assert service["image"] == f"mediadock/{role}:{revision}"
    assert service["build"]["args"]["IMAGE_REVISION"] == revision
    assert service["build"]["dockerfile"] == "docker/Dockerfile"
    assert service["build"]["target"] == role

assert set(config("normal")["services"]) == {"consumer"}
consumer = config("consumer")
normal = consumer["services"]["consumer"]
overload = consumer["services"]["consumer-overload"]
assert normal["volumes"][0]["source"] != overload["volumes"][0]["source"]
assert len({volume["name"] for volume in consumer["volumes"].values()}) == 2
for service in (normal, overload):
    prebuilt(service, "consumer")
    assert service["restart"] == "unless-stopped"
    assert service["healthcheck"]["test"][-1] == "http://127.0.0.1:8080/health"
    assert service["volumes"][0]["target"] == "/data"
    assert args(service)["--data"] == "/data"
    assert args(service)["--web"] == "/opt/mediadock/web"

assert ports(normal) == {("127.0.0.1", 50051, 50051), ("127.0.0.1", 8080, 8080)}
assert ports(overload) == {("127.0.0.1", 50052, 50051), ("127.0.0.1", 8081, 8080)}
assert (args(normal)["--c"], args(normal)["--q"]) == ("2", "5")
assert "--demo-delay-ms" not in args(normal)
assert (args(overload)["--c"], args(overload)["--q"], args(overload)["--demo-delay-ms"]) == ("1", "2", "2500")

producer = config("producer")["services"]["producer"]
prebuilt(producer, "producer")
assert producer["restart"] == "no"
assert producer["volumes"][0]["type"] == "bind"
assert producer["volumes"][0]["target"] == "/samples"
assert producer["volumes"][0]["read_only"]
assert not producer["volumes"][0]["bind"]["create_host_path"]
assert (args(producer)["--p"], args(producer)["--server"]) == ("3", "127.0.0.1:50051")
print("PASS Compose build targets, private port bindings, isolated volumes and one-shot producer")
PY
