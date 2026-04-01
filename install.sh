#!/usr/bin/env bash
# Install Self-Developing Coding Agent — platform-agnostic.
#
# Works on any system where the agent has read/write/shell access.
# Optional --openclaw flag adds OpenClaw-specific wiring.
#
# Usage:
#   # Deploy a headless Coding Agent alongside your Main Agent:
#   bash install.sh --agent-workspace /path/to/coding-agent --main-workspace /path/to/main-agent
#
#   # Same, with OpenClaw integration (patches openclaw.json, restarts gateway):
#   bash install.sh --agent-workspace /path/to/coding-agent --main-workspace /path/to/main-agent --openclaw
#
#   # Add dev skills to an existing agent (no new workspace):
#   bash install.sh --mode extend --agent-workspace /path/to/existing-agent
#
#   # Dry run:
#   bash install.sh --agent-workspace /tmp/test --main-workspace /tmp/main --dry-run
#
# Exit codes: 0=success, 1=warnings, 2=fatal, 3=config missing

set -euo pipefail

# ---------------------------------------------------------------------------
# Defaults
# ---------------------------------------------------------------------------
MODE="new"
AGENT_WORKSPACE=""
MAIN_WORKSPACE=""
OPENCLAW=false
OPENCLAW_AGENT_ID="dev-agent"
OPENCLAW_AGENT_NAME="Dev Agent"
DRY_RUN=false

# ---------------------------------------------------------------------------
# Parse arguments
# ---------------------------------------------------------------------------
while [[ $# -gt 0 ]]; do
    case $1 in
        --mode)
            MODE="$2"
            shift 2
            ;;
        --agent-workspace)
            AGENT_WORKSPACE="$2"
            shift 2
            ;;
        --main-workspace)
            MAIN_WORKSPACE="$2"
            shift 2
            ;;
        --openclaw)
            OPENCLAW=true
            shift
            ;;
        --agent-id)
            OPENCLAW_AGENT_ID="$2"
            shift 2
            ;;
        --agent-name)
            OPENCLAW_AGENT_NAME="$2"
            shift 2
            ;;
        --dry-run)
            DRY_RUN=true
            shift
            ;;
        -h|--help)
            cat << 'HELPEOF'
Usage: bash install.sh [OPTIONS]

Required:
  --agent-workspace DIR   Path to the Coding Agent's workspace directory
  --main-workspace DIR    Path to the Main Agent's workspace (for routing rules)

Modes:
  --mode new              Create a new Coding Agent workspace (default)
  --mode extend           Add dev skills to an existing agent workspace

Platform-specific:
  --openclaw              Enable OpenClaw integration (patch openclaw.json, create auth, restart gateway)
  --agent-id ID           OpenClaw agent ID (default: dev-agent)
  --agent-name NAME       OpenClaw agent display name (default: Dev Agent)

Common:
  --dry-run               Show what would be done without making changes
  -h, --help              Show this help
HELPEOF
            exit 0
            ;;
        *)
            echo "ERROR: Unknown argument: $1" >&2
            exit 2
            ;;
    esac
done

# ---------------------------------------------------------------------------
# Validate
# ---------------------------------------------------------------------------
if [[ -z "$AGENT_WORKSPACE" ]]; then
    echo "ERROR: --agent-workspace is required" >&2
    exit 2
fi

if [[ "$MODE" == "new" && -z "$MAIN_WORKSPACE" ]]; then
    echo "ERROR: --mode new requires --main-workspace" >&2
    exit 2
fi

if [[ "$MODE" == "new" && -n "$MAIN_WORKSPACE" && ! -d "$MAIN_WORKSPACE" ]]; then
    echo "ERROR: Main agent workspace not found: $MAIN_WORKSPACE" >&2
    exit 3
fi

if [[ "$MODE" != "new" && "$MODE" != "extend" ]]; then
    echo "ERROR: --mode must be 'new' or 'extend'" >&2
    exit 2
fi

if $OPENCLAW && ! command -v jq &>/dev/null; then
    echo "ERROR: --openclaw requires jq. Install it: apt install jq" >&2
    exit 2
fi

# ---------------------------------------------------------------------------
# Detect framework source
# ---------------------------------------------------------------------------
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

# Framework root is either this directory (if install.sh is at root)
# or two levels up (if running from deploy/openclaw/)
if [[ -f "$SCRIPT_DIR/BOOTSTRAP.md" ]]; then
    FRAMEWORK_SRC="$SCRIPT_DIR"
elif [[ -f "$SCRIPT_DIR/../../BOOTSTRAP.md" ]]; then
    FRAMEWORK_SRC="$(cd "$SCRIPT_DIR/../.." && pwd)"
else
    echo "ERROR: Cannot find framework root (looking for BOOTSTRAP.md)" >&2
    exit 3
fi

# Where to install the framework on the server
FRAMEWORK_DEST="${SDA_INSTALL_DIR:-$HOME/.sda-framework}"

echo "=== Installing Self-Developing Coding Agent ==="
echo ""
echo "  Mode:           $MODE"
echo "  Agent Workspace: $AGENT_WORKSPACE"
[[ -n "$MAIN_WORKSPACE" ]] && echo "  Main Workspace:  $MAIN_WORKSPACE"
echo "  Framework Src:  $FRAMEWORK_SRC"
echo "  Framework Dest: $FRAMEWORK_DEST"
echo "  OpenClaw:       $OPENCLAW"
echo "  Dry Run:        $DRY_RUN"
echo ""

# ===================================================================
# STEP 1: Copy framework to a permanent location
# ===================================================================
echo "Step 1: Copying framework to $FRAMEWORK_DEST ..."

if ! $DRY_RUN; then
    mkdir -p "$FRAMEWORK_DEST"
    if command -v rsync &>/dev/null; then
        rsync -a --delete \
            --exclude='__pycache__' \
            --exclude='*.pyc' \
            --exclude='.git/' \
            --exclude='test/' \
            --exclude='skills/*/scripts/test_*.py' \
            "$FRAMEWORK_SRC/" "$FRAMEWORK_DEST/"
    else
        # Fallback: plain cp
        rm -rf "$FRAMEWORK_DEST"
        cp -r "$FRAMEWORK_SRC" "$FRAMEWORK_DEST"
        find "$FRAMEWORK_DEST" -type d -name '__pycache__' -exec rm -rf {} + 2>/dev/null || true
        find "$FRAMEWORK_DEST" -name 'test_*.py' -delete 2>/dev/null || true
    fi
    echo "  Done."
else
    echo "  [DRY RUN] Would copy $FRAMEWORK_SRC/ -> $FRAMEWORK_DEST/"
fi

# ===================================================================
# STEP 2: Set up workspace
# ===================================================================
echo ""
echo "Step 2: Setting up workspace at $AGENT_WORKSPACE ..."

if ! $DRY_RUN; then
    mkdir -p "$AGENT_WORKSPACE/skills"
    mkdir -p "$AGENT_WORKSPACE/tasks"
    mkdir -p "$AGENT_WORKSPACE/delivery"

    if [[ "$MODE" == "new" ]]; then
        # Copy behavioral templates (AGENTS.md, HEARTBEAT.md, MEMORY.md)
        echo "  Copying behavioral files..."
        cp "$FRAMEWORK_DEST/skills/dev-bootstrap/templates/AGENTS.md" "$AGENT_WORKSPACE/"
        cp "$FRAMEWORK_DEST/skills/dev-bootstrap/templates/HEARTBEAT.md" "$AGENT_WORKSPACE/"
        cp "$FRAMEWORK_DEST/skills/dev-bootstrap/templates/MEMORY.md" "$AGENT_WORKSPACE/"

        # Copy identity templates if they exist (OpenClaw-specific templates)
        if [[ -d "$FRAMEWORK_DEST/deploy/openclaw/templates" ]]; then
            echo "  Copying identity files..."
            for tmpl in IDENTITY.md SOUL.md USER.md TOOLS.md; do
                [[ -f "$FRAMEWORK_DEST/deploy/openclaw/templates/$tmpl" ]] && \
                    cp "$FRAMEWORK_DEST/deploy/openclaw/templates/$tmpl" "$AGENT_WORKSPACE/"
            done
        fi

    else
        # Extend mode: add dev rules to existing workspace
        if [[ -f "$AGENT_WORKSPACE/AGENTS.md" ]] && ! grep -q "# Self-Development Extension" "$AGENT_WORKSPACE/AGENTS.md" 2>/dev/null; then
            echo "  Appending dev lifecycle rules to existing AGENTS.md..."
            echo "" >> "$AGENT_WORKSPACE/AGENTS.md"
            echo "---" >> "$AGENT_WORKSPACE/AGENTS.md"
            echo "" >> "$AGENT_WORKSPACE/AGENTS.md"
            echo "# Self-Development Extension" >> "$AGENT_WORKSPACE/AGENTS.md"
            echo "" >> "$AGENT_WORKSPACE/AGENTS.md"
            echo "Dev skills installed: dev-bootstrap, dev-sprint, dev-critique, dev-deploy" >> "$AGENT_WORKSPACE/AGENTS.md"
            echo "Read each skill's SKILL.md for commands and usage." >> "$AGENT_WORKSPACE/AGENTS.md"
            echo "For the full development lifecycle, read: skills/dev-bootstrap/templates/AGENTS.md" >> "$AGENT_WORKSPACE/AGENTS.md"
        elif [[ -f "$AGENT_WORKSPACE/AGENTS.md" ]]; then
            echo "  Dev extension already present — skipping"
        else
            echo "  No existing AGENTS.md — copying full version..."
            cp "$FRAMEWORK_DEST/skills/dev-bootstrap/templates/AGENTS.md" "$AGENT_WORKSPACE/"
        fi

        # Copy TOOLS.md (skill reference)
        if [[ -d "$FRAMEWORK_DEST/deploy/openclaw/templates" ]]; then
            cp "$FRAMEWORK_DEST/deploy/openclaw/templates/TOOLS.md" "$AGENT_WORKSPACE/" 2>/dev/null || true
        fi
    fi

    echo "  Done."
else
    echo "  [DRY RUN] Would set up workspace at $AGENT_WORKSPACE"
fi

# ===================================================================
# STEP 3: Copy skills into workspace
# ===================================================================
echo ""
echo "Step 3: Copying dev skills..."

SKILLS="dev-bootstrap dev-sprint dev-critique dev-deploy"
for skill_name in $SKILLS; do
    if [[ ! -d "$FRAMEWORK_DEST/skills/$skill_name" ]]; then
        echo "  WARNING: Skill not found: $skill_name" >&2
        continue
    fi
    echo "  -> $skill_name"
    if ! $DRY_RUN; then
        rm -rf "$AGENT_WORKSPACE/skills/$skill_name"
        cp -r "$FRAMEWORK_DEST/skills/$skill_name" "$AGENT_WORKSPACE/skills/"
        find "$AGENT_WORKSPACE/skills/$skill_name" -type d -name '__pycache__' -exec rm -rf {} + 2>/dev/null || true
        find "$AGENT_WORKSPACE/skills/$skill_name" -name 'test_*.py' -delete 2>/dev/null || true
    fi
done

if $DRY_RUN; then
    echo "  [DRY RUN] Would copy: $SKILLS"
fi

# ===================================================================
# STEP 4: Wire Main Agent routing (new mode only)
# ===================================================================
ROUTING_TARGET=""  # Track where routing rules ended up

if [[ "$MODE" == "new" && -n "$MAIN_WORKSPACE" ]]; then
    echo ""
    echo "Step 4: Wiring Main Agent routing..."

    if ! $DRY_RUN; then
        ROUTING_TEMPLATE="$FRAMEWORK_DEST/deploy/openclaw/templates/MAIN_AGENT_ROUTING.md"
        ROUTING_CONTENT=""
        if [[ -f "$ROUTING_TEMPLATE" ]]; then
            ROUTING_CONTENT=$(sed "s|{{CODING_AGENT_TASKS_DIR}}|$AGENT_WORKSPACE/tasks|g; s|{{CODING_AGENT_WORKSPACE}}|$AGENT_WORKSPACE|g" \
                "$ROUTING_TEMPLATE")
        fi

        if [[ -f "$MAIN_WORKSPACE/AGENTS.md" ]]; then
            if grep -q "# Coding Agent Delegation" "$MAIN_WORKSPACE/AGENTS.md" 2>/dev/null; then
                ROUTING_TARGET="$MAIN_WORKSPACE/AGENTS.md"
                echo "  Routing rules already present — skipping"
            elif [[ -w "$MAIN_WORKSPACE/AGENTS.md" ]]; then
                {
                    echo ""
                    echo "---"
                    echo ""
                    echo "$ROUTING_CONTENT"
                } >> "$MAIN_WORKSPACE/AGENTS.md"
                ROUTING_TARGET="$MAIN_WORKSPACE/AGENTS.md"
                echo "  Routing rules appended to $MAIN_WORKSPACE/AGENTS.md"
            else
                # AGENTS.md is not writable (e.g. root-owned, read-only) — write to a separate file
                echo "  WARNING: $MAIN_WORKSPACE/AGENTS.md is not writable ($(ls -l "$MAIN_WORKSPACE/AGENTS.md" 2>/dev/null | awk '{print $3":"$4, $1}'))" >&2
                echo "$ROUTING_CONTENT" > "$MAIN_WORKSPACE/ROUTING.md" 2>/dev/null && {
                    ROUTING_TARGET="$MAIN_WORKSPACE/ROUTING.md"
                    echo "  Routing rules saved to $MAIN_WORKSPACE/ROUTING.md instead"
                    echo "  To merge: make AGENTS.md writable, then append ROUTING.md contents" >&2
                } || {
                    echo "  WARNING: Could not write ROUTING.md either. Saving to $AGENT_WORKSPACE/ROUTING.md" >&2
                    echo "$ROUTING_CONTENT" > "$AGENT_WORKSPACE/ROUTING.md"
                    ROUTING_TARGET="$AGENT_WORKSPACE/ROUTING.md"
                    echo "  Routing rules saved to $AGENT_WORKSPACE/ROUTING.md — copy to main workspace manually" >&2
                }
            fi
        elif [[ ! -f "$MAIN_WORKSPACE/AGENTS.md" ]]; then
            echo "  WARNING: $MAIN_WORKSPACE/AGENTS.md not found — routing rules not appended" >&2
            echo "  The Main Agent needs routing rules to delegate tasks. See deploy/openclaw/templates/MAIN_AGENT_ROUTING.md" >&2
        fi
    else
        echo "  [DRY RUN] Would append routing rules to $MAIN_WORKSPACE/AGENTS.md"
    fi
else
    echo ""
    echo "Step 4: Skipped (extend mode or no main workspace)"
fi

# ===================================================================
# STEP 5: Set SDA_FRAMEWORK_ROOT
# ===================================================================
echo ""
echo "Step 5: Framework root configuration..."
echo "  SDA_FRAMEWORK_ROOT=$FRAMEWORK_DEST"
echo "  Skills use this to find roles/, practices/, templates/"
echo ""
echo "  Set this environment variable for your agent platform:"
echo "    export SDA_FRAMEWORK_ROOT=$FRAMEWORK_DEST"

# ===================================================================
# STEP 6: OpenClaw-specific wiring (optional)
# ===================================================================
if $OPENCLAW; then
    echo ""
    echo "Step 6: OpenClaw integration..."

    # Detect OpenClaw root
    OPENCLAW_ROOT=""
    if [[ -d "/home/openclaw/.openclaw" ]]; then
        OPENCLAW_ROOT="/home/openclaw/.openclaw"
    elif [[ -d "$HOME/.openclaw" ]]; then
        OPENCLAW_ROOT="$HOME/.openclaw"
    fi

    if [[ -z "$OPENCLAW_ROOT" ]]; then
        echo "  WARNING: OpenClaw root not found. Skipping OpenClaw wiring." >&2
        echo "  Checked: /home/openclaw/.openclaw and $HOME/.openclaw" >&2
    else
        CONFIG_FILE="$OPENCLAW_ROOT/openclaw.json"
        AGENT_DIR="$OPENCLAW_ROOT/agents/$OPENCLAW_AGENT_ID/agent"

        if [[ "$MODE" == "new" ]] && ! $DRY_RUN; then
            # Create agent auth directory
            echo "  Creating agent auth directory..."
            mkdir -p "$AGENT_DIR"

            MAIN_AUTH="$OPENCLAW_ROOT/agents/main/agent/auth-profiles.json"
            if [[ -f "$MAIN_AUTH" && -s "$MAIN_AUTH" ]]; then
                cp "$MAIN_AUTH" "$AGENT_DIR/auth-profiles.json"
            else
                echo "  WARNING: Main agent auth not found at $MAIN_AUTH" >&2
                echo "  Create $AGENT_DIR/auth-profiles.json manually with your API key" >&2
            fi

            cat > "$AGENT_DIR/models.json" << 'MODELSEOF'
{
  "default": "anthropic/claude-sonnet-4-6"
}
MODELSEOF
            echo '{}' > "$AGENT_DIR/auth.json"

            # Create workspace-state.json
            mkdir -p "$AGENT_WORKSPACE/.openclaw"
            cat > "$AGENT_WORKSPACE/.openclaw/workspace-state.json" << WSEOF
{
  "version": 1,
  "onboardingCompletedAt": "$(date -u +%Y-%m-%dT%H:%M:%S.000Z)"
}
WSEOF
        fi

        # Patch openclaw.json
        if [[ -f "$CONFIG_FILE" ]] && ! $DRY_RUN; then
            if [[ ! -w "$CONFIG_FILE" ]]; then
                echo "  WARNING: $CONFIG_FILE is not writable — skipping config patching" >&2
                echo "  You will need to register the dev-agent and skills manually" >&2
            else
                cp "$CONFIG_FILE" "${CONFIG_FILE}.bak.$(date +%s)"

                if [[ "$MODE" == "new" ]]; then
                    # Register agent — ensure .agents.list exists
                    AGENT_EXISTS=$(jq --arg id "$OPENCLAW_AGENT_ID" '(.agents.list // []) | map(select(.id == $id)) | length' "$CONFIG_FILE")
                    if [[ "$AGENT_EXISTS" == "0" ]]; then
                        jq --arg id "$OPENCLAW_AGENT_ID" \
                           --arg name "$OPENCLAW_AGENT_NAME" \
                           --arg ws "$AGENT_WORKSPACE" \
                           --arg ad "$AGENT_DIR" \
                           '.agents.list = ((.agents.list // []) + [{
                               "id": $id,
                               "name": $name,
                               "workspace": $ws,
                               "agentDir": $ad,
                               "heartbeat": { "every": "10m" }
                           }])' "$CONFIG_FILE" > "${CONFIG_FILE}.tmp" && mv "${CONFIG_FILE}.tmp" "$CONFIG_FILE"
                        echo "  Added agent '$OPENCLAW_AGENT_ID' to openclaw.json"
                    fi
                fi

                # Register skills — ensure .skills.entries exists
                for skill_name in $SKILLS; do
                    SKILL_EXISTS=$(jq --arg name "$skill_name" '(.skills.entries // {}) | has($name)' "$CONFIG_FILE")
                    if [[ "$SKILL_EXISTS" == "false" ]]; then
                        jq --arg name "$skill_name" \
                           --arg fw "$FRAMEWORK_DEST" \
                           '.skills.entries = ((.skills.entries // {}) + {($name): { "env": { "SDA_FRAMEWORK_ROOT": $fw } }})' \
                           "$CONFIG_FILE" > "${CONFIG_FILE}.tmp" && mv "${CONFIG_FILE}.tmp" "$CONFIG_FILE"
                        echo "  Registered skill '$skill_name'"
                    fi
                done
            fi
        fi

        # Set permissions
        if ! $DRY_RUN; then
            chown -R openclaw:openclaw "$AGENT_WORKSPACE" "$FRAMEWORK_DEST" 2>/dev/null || true
            [[ -d "$AGENT_DIR" ]] && chown -R openclaw:openclaw "$AGENT_DIR" 2>/dev/null || true
            find "$AGENT_WORKSPACE/skills" -name '*.py' -exec chmod 550 {} \; 2>/dev/null || true
        fi

        # Restart gateway
        if ! $DRY_RUN && command -v systemctl &>/dev/null; then
            echo "  Restarting openclaw-gateway..."
            systemctl restart openclaw-gateway 2>/dev/null && {
                echo "  Gateway restarted."
            } || {
                echo "  WARNING: Could not restart gateway. Run: sudo systemctl restart openclaw-gateway" >&2
            }
        fi
    fi
else
    echo ""
    echo "Step 6: Skipped (no --openclaw flag)"
fi

# ===================================================================
# Done
# ===================================================================
echo ""
echo "========================================"
echo "  Installation complete!"
echo "========================================"
echo ""

if [[ "$MODE" == "new" ]]; then
    echo "Coding Agent workspace:  $AGENT_WORKSPACE"
    echo "Task directory:          $AGENT_WORKSPACE/tasks/"
    echo "Delivery reports:        $AGENT_WORKSPACE/delivery/"
    echo "Framework location:      $FRAMEWORK_DEST"
    echo ""
    if [[ -n "$MAIN_WORKSPACE" ]]; then
        if [[ -n "$ROUTING_TARGET" ]]; then
            echo "Main Agent wiring:       Routing rules written to $ROUTING_TARGET"
        else
            echo "Main Agent wiring:       Routing rules not written (see warnings above)"
        fi
        echo ""
    fi
    echo "--- NEXT STEPS ---"
    echo ""
    echo "1. Set the framework root for your agent platform:"
    echo "   export SDA_FRAMEWORK_ROOT=$FRAMEWORK_DEST"
    echo ""
    if $OPENCLAW; then
        echo "2. The gateway has been restarted. The Coding Agent is polling for tasks."
        echo ""
        echo "3. Tell your Main Agent: 'Read your updated AGENTS.md — you can now delegate coding tasks.'"
        echo ""
    else
        echo "2. Configure your agent platform to load the Coding Agent with:"
        echo "   - Workspace: $AGENT_WORKSPACE"
        echo "   - Read AGENTS.md and HEARTBEAT.md on session start"
        echo "   - Run poll-tasks.py every 10 minutes (or on heartbeat)"
        echo ""
        echo "3. Tell your Main Agent about the routing rules in its updated AGENTS.md."
        echo ""
    fi
else
    echo "Dev skills added to: $AGENT_WORKSPACE"
    echo ""
    echo "Skills installed: dev-bootstrap, dev-sprint, dev-critique, dev-deploy"
    echo "Tell your agent: 'Read TOOLS.md and each dev skill SKILL.md to learn your new capabilities.'"
fi

exit 0
