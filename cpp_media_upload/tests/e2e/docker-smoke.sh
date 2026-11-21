#!/usr/bin/env bash
set -euo pipefail

cd "$(dirname "$0")/../.."
: "${IMAGE_REVISION:?set the full source Git commit SHA}"
: "${CONSUMER_PRIVATE_IP:?set the consumer guest private IPv4 address}"
[[ $IMAGE_REVISION =~ ^[a-f0-9]{40}$ ]] || {
  printf 'IMAGE_REVISION must be a full Git commit SHA\n' >&2
  exit 2
}

compose_file=infra/${1:-invalid}.compose.yml
compose=(docker compose --project-name mediadock-docker-smoke -f "$compose_file")

verify_revision() {
  local revision
  revision=$(docker image inspect --format '{{index .Config.Labels "org.opencontainers.image.revision"}}' \
    "mediadock/$1:$IMAGE_REVISION")
  test "$revision" = "$IMAGE_REVISION"
}

case ${1:-} in
  producer)
    verify_revision producer
    "${compose[@]}" run --rm -T producer --help | grep -F 'Usage: media_producer'
    printf 'PASS producer image label and one-shot executable\n'
    ;;
  consumer)
    compose+=(--profile overload)
    verify_revision consumer
    for service in consumer consumer-overload; do
      "${compose[@]}" up -d --wait --wait-timeout 60 "$service"
      original_database=$("${compose[@]}" exec -T "$service" sh -ec '
        test "$(id -u)" = 10001
        test -w /data
        test -s /data/metadata.db
        stat -c %i /data/metadata.db
      ')
      original_container=$("${compose[@]}" ps -q "$service")
      "${compose[@]}" up -d --wait --wait-timeout 60 "$service"
      test "$("${compose[@]}" ps -q "$service")" = "$original_container"
      "${compose[@]}" up -d --force-recreate --wait --wait-timeout 60 "$service"
      recreated_container=$("${compose[@]}" ps -q "$service")
      test "$recreated_container" != "$original_container"
      test "$("${compose[@]}" exec -T "$service" stat -c %i /data/metadata.db)" = "$original_database"
      volume=$(docker inspect --format '{{range .Mounts}}{{if eq .Destination "/data"}}{{.Name}}{{end}}{{end}}' \
        "$recreated_container")
      if [ "$service" = consumer ]; then
        normal_volume=$volume
      else
        test "$volume" != "$normal_volume"
      fi
      test -n "$volume"
      "${compose[@]}" stop "$service"
      printf 'PASS %s health and preserved database in %s\n' "$service" "$volume"
    done
    ;;
  *)
    printf 'Usage: %s producer|consumer\n' "$0" >&2
    exit 2
    ;;
esac
