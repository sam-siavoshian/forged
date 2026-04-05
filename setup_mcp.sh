#!/usr/bin/env bash
# ──────────────────────────────────────────────────────────────────────
# Forged MCP Server — One-command setup for Claude Code
#
# Usage:
#   curl -fsSL https://raw.githubusercontent.com/sam-siavoshian/browser-use-rl-env/main/setup_mcp.sh | bash
#   — or —
#   bash setup_mcp.sh
# ──────────────────────────────────────────────────────────────────────
set -euo pipefail

# ── Colors ────────────────────────────────────────────────────────────
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[0;33m'
CYAN='\033[0;36m'
BOLD='\033[1m'
NC='\033[0m'

info()  { printf "${CYAN}▸${NC} %s\n" "$*"; }
ok()    { printf "${GREEN}✓${NC} %s\n" "$*"; }
warn()  { printf "${YELLOW}!${NC} %s\n" "$*"; }
fail()  { printf "${RED}✗${NC} %s\n" "$*"; exit 1; }

# ── Banner ────────────────────────────────────────────────────────────
printf "\n${BOLD}"
cat << 'BANNER'
  ╔═══════════════════════════════════════════════╗
  ║          ⚒  FORGED  MCP  SERVER  ⚒           ║
  ║   Self-improving browser automation for AI    ║
  ╚═══════════════════════════════════════════════╝
BANNER
printf "${NC}\n"

# ── Step 1: Check prerequisites ───────────────────────────────────────
info "Checking prerequisites..."

# Python 3.11+
if ! command -v python3 &>/dev/null && ! command -v python &>/dev/null; then
    fail "Python 3.11+ is required but not found. Install it first."
fi

PYTHON=$(command -v python3 || command -v python)
PY_VERSION=$("$PYTHON" -c 'import sys; print(f"{sys.version_info.major}.{sys.version_info.minor}")')
PY_MAJOR=$("$PYTHON" -c 'import sys; print(sys.version_info.major)')
PY_MINOR=$("$PYTHON" -c 'import sys; print(sys.version_info.minor)')

if [ "$PY_MAJOR" -lt 3 ] || { [ "$PY_MAJOR" -eq 3 ] && [ "$PY_MINOR" -lt 11 ]; }; then
    fail "Python 3.11+ required, found $PY_VERSION"
fi
ok "Python $PY_VERSION"

# Claude Code CLI
if ! command -v claude &>/dev/null; then
    fail "Claude Code CLI not found. Install it: https://docs.anthropic.com/en/docs/claude-code"
fi
ok "Claude Code CLI found"

# ── Step 2: Locate or clone the Forged repo ──────────────────────────
info "Looking for Forged installation..."

# Check if we're already inside the repo
if [ -f "mcp_server.py" ] && [ -f "src/api.py" ]; then
    FORGED_DIR="$(pwd)"
    ok "Found Forged in current directory: $FORGED_DIR"
else
    # Check common locations
    FORGED_DIR=""
    for candidate in \
        "$HOME/forged" \
        "$HOME/Desktop/forged" \
        "$HOME/Projects/forged" \
        "$HOME/Code/forged" \
        "$HOME/dev/forged"; do
        if [ -f "$candidate/mcp_server.py" ]; then
            FORGED_DIR="$candidate"
            break
        fi
    done

    if [ -z "$FORGED_DIR" ]; then
        printf "\n"
        printf "${YELLOW}Forged repo not found automatically.${NC}\n"
        printf "Enter the full path to your Forged project directory:\n"
        printf "${CYAN}> ${NC}"
        read -r FORGED_DIR

        # Expand ~ if present
        FORGED_DIR="${FORGED_DIR/#\~/$HOME}"

        if [ ! -f "$FORGED_DIR/mcp_server.py" ]; then
            fail "mcp_server.py not found in $FORGED_DIR"
        fi
    fi
    ok "Found Forged at: $FORGED_DIR"
fi

MCP_SERVER_PATH="$FORGED_DIR/mcp_server.py"

# ── Step 3: Check Python dependencies ────────────────────────────────
info "Checking Python dependencies..."

MISSING_DEPS=()

"$PYTHON" -c "import mcp" 2>/dev/null || MISSING_DEPS+=("mcp")
"$PYTHON" -c "import httpx" 2>/dev/null || MISSING_DEPS+=("httpx")

if [ ${#MISSING_DEPS[@]} -gt 0 ]; then
    warn "Missing packages: ${MISSING_DEPS[*]}"
    printf "  Install them now? [Y/n] "
    read -r INSTALL_DEPS
    INSTALL_DEPS=${INSTALL_DEPS:-Y}
    if [[ "$INSTALL_DEPS" =~ ^[Yy] ]]; then
        "$PYTHON" -m pip install "${MISSING_DEPS[@]}" --quiet
        ok "Installed: ${MISSING_DEPS[*]}"
    else
        fail "Cannot proceed without: ${MISSING_DEPS[*]}"
    fi
else
    ok "All dependencies installed (mcp, httpx)"
fi

# ── Step 4: Configure backend URL ────────────────────────────────────
DEFAULT_URL="http://localhost:8000"

printf "\n"
info "Where is the Forged backend running?"
printf "  Press Enter for default (${CYAN}$DEFAULT_URL${NC}), or enter a custom URL:\n"
printf "${CYAN}> ${NC}"
read -r BACKEND_URL
BACKEND_URL=${BACKEND_URL:-$DEFAULT_URL}

# Quick health check (non-blocking — backend might not be running yet)
if command -v curl &>/dev/null; then
    if curl -s --max-time 2 "$BACKEND_URL/api/health" &>/dev/null; then
        ok "Backend is reachable at $BACKEND_URL"
    else
        warn "Backend not reachable at $BACKEND_URL (that's OK — start it before using Forged)"
    fi
fi

# ── Step 5: Choose scope ─────────────────────────────────────────────
printf "\n"
info "Where should the MCP server be registered?"
printf "  ${BOLD}1)${NC} User scope — available in all your Claude Code sessions (recommended)\n"
printf "  ${BOLD}2)${NC} Project scope — only available in this project\n"
printf "  Choice [1/2]: "
read -r SCOPE_CHOICE
SCOPE_CHOICE=${SCOPE_CHOICE:-1}

case "$SCOPE_CHOICE" in
    1) SCOPE="user" ;;
    2) SCOPE="project" ;;
    *) SCOPE="user" ;;
esac

ok "Using $SCOPE scope"

# ── Step 6: Register with Claude Code ─────────────────────────────────
printf "\n"
info "Registering Forged MCP server with Claude Code..."

# Remove existing registration if present (ignore errors)
claude mcp remove forged -s "$SCOPE" 2>/dev/null || true

# Register using claude mcp add
claude mcp add \
    -s "$SCOPE" \
    -e "FORGED_API_URL=$BACKEND_URL" \
    forged \
    -- \
    "$PYTHON" "$MCP_SERVER_PATH"

ok "Forged MCP server registered!"

# ── Step 7: Verify ───────────────────────────────────────────────────
printf "\n"
info "Verifying registration..."

if claude mcp get forged -s "$SCOPE" &>/dev/null; then
    ok "Verified: 'forged' MCP server is registered"
else
    warn "Could not verify registration. Try: claude mcp list"
fi

# ── Done ──────────────────────────────────────────────────────────────
printf "\n"
printf "${BOLD}${GREEN}════════════════════════════════════════════════${NC}\n"
printf "${BOLD}${GREEN}  Forged MCP Server is ready!${NC}\n"
printf "${BOLD}${GREEN}════════════════════════════════════════════════${NC}\n"
printf "\n"
printf "  ${BOLD}Before using:${NC}\n"
printf "    1. Start the Forged backend:\n"
printf "       ${CYAN}cd $FORGED_DIR && ./dev.sh${NC}\n"
printf "\n"
printf "    2. Restart Claude Code (or start a new session)\n"
printf "\n"
printf "  ${BOLD}Then try:${NC}\n"
printf "    Ask Claude Code to run a browser task:\n"
printf "    ${CYAN}\"Go to news.ycombinator.com and get the top story\"${NC}\n"
printf "\n"
printf "    The first run uses a full AI agent.\n"
printf "    The second run is ${BOLD}faster${NC} — learned steps replay via Playwright.\n"
printf "\n"
printf "  ${BOLD}Manage:${NC}\n"
printf "    ${CYAN}claude mcp list${NC}           — see registered servers\n"
printf "    ${CYAN}claude mcp get forged${NC}     — check Forged config\n"
printf "    ${CYAN}claude mcp remove forged${NC}  — uninstall\n"
printf "\n"
