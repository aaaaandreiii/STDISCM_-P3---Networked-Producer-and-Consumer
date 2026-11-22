# MediaDock demo on the Mac

After [one-time Acer and guest setup](VM_SETUP.md), run the following commands from `cpp_media_upload/`. The Mac needs Bash, Python 3.11 or later, and OpenSSH.

| Command | Result |
| --- | --- |
| `./demo.sh start` | Starts or resumes the two enrolled VMs, restores the normal consumer, checks HTTP and gRPC readiness and prints the local GUI URL. |
| `./demo.sh` | Runs normal uploads, duplicate handling, compression and queue overload. Restores the normal gallery and opens it on the Mac. |
| `./demo.sh status` | Reports the Acer, guest, container, health and tunnel states and the latest local evidence. |
| `./demo.sh stop` | Waits for uploads and processing to finish, stops MediaDock services and both guests gracefully, closes the owned SSH tunnel and reports the host RAM, swap and disk readings. |

## Configure once

Copy `.env.demo.example` to `.env.demo` and fill in the owners' verified settings. Entries use plain `KEY=value` lines. Keep SSH credentials and this configuration out of Git.

- Set `UBUNTU_LAPTOP_SSH`, `PRODUCER_SSH` and `CONSUMER_SSH` to the three verified SSH aliases. The guest aliases use the Acer as their jump host. Check each alias from the Mac with `ssh -o BatchMode=yes -o StrictHostKeyChecking=yes <alias> hostname` when the guests are provisioned and running. Keep the dedicated key loaded in the Mac login SSH agent for password-free use from each Terminal.
- Set `CONSUMER_PRIVATE_IP` to the consumer's reserved address and copy each guest's `/etc/machine-id` into the matching configuration field. Set `IMAGE_REVISION` to the full deployed SHA. Confirm its stamped release is present on both guests and the corresponding image is already loaded in each rootless Docker daemon.
- Use the default GUI address `http://127.0.0.1:8080` or set `GUI_BASE_URL` to another unused local port. Keep the Acer alias free of its own forwards. The GUI shows normal service after the default command finishes.

Normal lifecycle commands require the root-owned `mediadock-vmctl` wrapper and the specific sudoers rules documented in the setup runbook. The guest users run their own rootless Docker daemons through SSH. The two VMs, images and guest tools can be reused on later runs.

## Read the results

Each start, demo or stop writes `.demo-evidence/<run-id>/summary.json` and prints its full path. A demo includes fixture hashes, producer logs and receipts, measured resource and queue metrics, published media properties and HTTP Range checks. A browser opens after the normal gallery is restored. Hover over a video for the muted preview. Click to play and seek in the full video. Record an actual browser interaction separately from the automated HTTP results.

A shutdown failure exits nonzero and leaves the evidence and any still-reachable services for inspection. Run `./demo.sh status` to see which component remains available, then retry after active work drains. Uploaded files, databases, images and volumes remain on the guests.
