# First Codex session: exact Mac + Ubuntu instructions to paste

**Model:** use **High reasoning** for master P0 if your Codex selector supports it (the user called this “GPT-6.2-Sol High”; actual labels may differ). Use Medium for A/B scoped implementation; no more than **two worker agents concurrently**.

```text
You are the MASTER ORCHESTRATOR for my MediaDock C++20 project. This implementation plan is APPROVED by me on 2026-11-21. Do NOT ask me for generic plan approval again. You have permission to implement application code and create Docker/VM provisioning scripts in the specified phases, but do NOT execute privileged changes to my machines (sudo/apt, hypervisor VM creation, firewall, SSH configuration, user/group permissions or destructive operations) until you show the exact operations and I explicitly approve them.

Environment: My primary computer is a base-model Apple M4 MacBook Air running macOS. I can SSH from it to a spare physical Ubuntu laptop, but there are no Ubuntu virtual machines yet. The instructor permits Docker containers inside TWO ACTUAL SEPARATE Ubuntu VMs. Prefer making two KVM/libvirt Ubuntu guest VMs on the spare laptop if a read-only hardware preflight finds sufficient virtualization support, memory and disk. The Mac is the Codex/terminal/browser host, and the Ubuntu laptop is the hypervisor/jump host (NOT one of the two VMs). If hardware cannot support that, recommend a truly two-guest fallback and ask only necessary questions. Never make up guest IPs/SSH usernames.

Read AGENTS.md, TODO.md, docs/02_DECISIONS_AND_APPROVAL.md, docs/10_MAC_UBUNTU_HOST_TOPOLOGY.md, docs/04_PHASE_MAP_AND_OWNERSHIP.md, and phases/P0_MASTER_BASELINE.md. Execute P0 only first: verify current git/source tree, run safe read-only SSH hardware preflight if the laptop SSH alias is known, record physical/guest topology and resource estimates, freeze source contracts, establish isolated worktrees/branches, define tests/ownership, and report P0 gate results. Do not spawn the implementation workers until P0 is complete. After P0, coordinate no more than TWO parallel sub-agents: A implements P1 -> P2 -> P6 (core/gRPC); B implements P3 -> P4 -> P5 (Docker/GUI/demo), with merge gates and no overlapping files. I want only one terminal command ./demo.sh on my Mac to resume/create the necessary containers and exercise the project, after one-time VM/bootstrap setup. It must open/print the GUI via a managed localhost SSH tunnel and preserve videos on reruns. Slides, recording, and a verbal presentation script are TODO-only; do not implement them.

Keep token use efficient. Start by confirming APPROVED status, read-only Ubuntu laptop preflight checks and their results (or the one missing SSH alias), proposed two-guest topology, and exact file ownership for Wave 1.
```

**Project source:** if using the integrated ZIP, open its `cpp_media_upload/` folder in Codex before sending this prompt. Do not paste the full ZIP contents into chat.
