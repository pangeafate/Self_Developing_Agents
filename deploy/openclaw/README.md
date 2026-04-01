# OpenClaw-Specific Setup Guide

The main installer (`install.sh` at the framework root) handles everything platform-agnostic. This guide covers OpenClaw-specific details.

## Quick Start

```bash
git clone <repo-url> /tmp/sda-install

# Deploy headless Coding Agent with OpenClaw integration:
bash /tmp/sda-install/install.sh \
  --agent-workspace /home/openclaw/.openclaw/workspace-dev-agent \
  --main-workspace /home/openclaw/.openclaw/workspace \
  --openclaw --agent-id dev-agent

# Or extend your existing agent:
bash /tmp/sda-install/install.sh \
  --mode extend \
  --agent-workspace /home/openclaw/.openclaw/workspace \
  --openclaw
```

## What `--openclaw` Adds

On top of the generic install, the `--openclaw` flag:

1. Creates agent auth directory (`~/.openclaw/agents/<id>/agent/`) with auth-profiles.json copied from the main agent
2. Creates `workspace-state.json` at `.openclaw/workspace-state.json` (required for OpenClaw workspace recognition)
3. Patches `openclaw.json` to register the agent and 4 dev skills (with `SDA_FRAMEWORK_ROOT` env var)
4. Sets file permissions (`openclaw:openclaw`, 550 for .py, 440 for .md)
5. Restarts `openclaw-gateway`

## Prerequisites

- OpenClaw installed on a VM with a `main` agent configured
- Anthropic API key in the main agent's `auth-profiles.json`
- `jq` installed (`apt install jq`)

## Verification

```bash
# Gateway running
systemctl status openclaw-gateway

# Skills registered
jq '.skills.entries | keys[]' ~/.openclaw/openclaw.json | grep dev-

# Skills in workspace
ls ~/.openclaw/workspace-dev-agent/skills/ | grep dev-
```

## Troubleshooting

### Gateway won't start
```bash
journalctl -u openclaw-gateway -n 50 --no-pager
```
Common cause: invalid JSON in openclaw.json. Validate: `jq . ~/.openclaw/openclaw.json`

### Permissions
```bash
chown -R openclaw:openclaw /home/openclaw/.openclaw/workspace-dev-agent
chown -R openclaw:openclaw /home/openclaw/self-developing-agents
```
