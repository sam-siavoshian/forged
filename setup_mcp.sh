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

# ── Theme ─────────────────────────────────────────────────────────────
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[0;33m'
BLUE='\033[0;34m'
MAGENTA='\033[0;35m'
CYAN='\033[0;36m'
DIM='\033[2m'
BOLD='\033[1m'
ITALIC='\033[3m'
NC='\033[0m'
BAR="${DIM}│${NC}"

# Clack-inspired primitives
step_start() {
    printf "${DIM}│${NC}\n"
    printf "${GREEN}◆${NC}  ${BOLD}%s${NC}\n" "$1"
}
step_ok() {
    printf "${BAR}  ${GREEN}✓${NC} %s\n" "$1"
}
step_warn() {
    printf "${BAR}  ${YELLOW}▲${NC} %s\n" "$1"
}
step_fail() {
    printf "${BAR}  ${RED}■${NC} %s\n" "$1"
    printf "${DIM}│${NC}\n"
    printf "${RED}◼${NC}  ${RED}Setup failed.${NC}\n\n"
    exit 1
}
step_info() {
    printf "${BAR}  ${DIM}%s${NC}\n" "$1"
}
step_end() {
    printf "${DIM}│${NC}\n"
}
spinner() {
    local pid=$1 msg=$2
    local frames=("⠋" "⠙" "⠹" "⠸" "⠼" "⠴" "⠦" "⠧" "⠇" "⠏")
    local i=0
    while kill -0 "$pid" 2>/dev/null; do
        printf "\r${BAR}  ${MAGENTA}${frames[$i]}${NC} ${DIM}%s${NC}" "$msg"
        i=$(( (i + 1) % ${#frames[@]} ))
        sleep 0.08
    done
    printf "\r${BAR}  ${GREEN}✓${NC} %s\n" "$msg"
}
prompt_input() {
    local label="$1" default="$2" var_name="$3"
    if [ -n "$default" ]; then
        printf "${BAR}  ${BOLD}%s${NC} ${DIM}(%s)${NC}\n" "$label" "$default"
    else
        printf "${BAR}  ${BOLD}%s${NC}\n" "$label"
    fi
    printf "${BAR}  ${CYAN}❯${NC} "
    local input
    read -r input </dev/tty
    eval "$var_name=\"\${input:-$default}\""
}
prompt_select() {
    local label="$1" opt1="$2" opt2="$3" default="$4" var_name="$5"
    printf "${BAR}  ${BOLD}%s${NC}\n" "$label"
    if [ "$default" = "1" ]; then
        printf "${BAR}    ${GREEN}●${NC} ${BOLD}%s${NC}\n" "$opt1"
        printf "${BAR}    ${DIM}○${NC} ${DIM}%s${NC}\n" "$opt2"
    else
        printf "${BAR}    ${DIM}○${NC} ${DIM}%s${NC}\n" "$opt1"
        printf "${BAR}    ${GREEN}●${NC} ${BOLD}%s${NC}\n" "$opt2"
    fi
    printf "${BAR}  ${DIM}Enter 1 or 2${NC} ${CYAN}❯${NC} "
    local choice
    read -r choice </dev/tty
    eval "$var_name=\"\${choice:-$default}\""
}
prompt_confirm() {
    local label="$1" var_name="$2"
    printf "${BAR}  %s ${DIM}(Y/n)${NC} ${CYAN}❯${NC} " "$label"
    local answer
    read -r answer </dev/tty
    eval "$var_name=\"\${answer:-Y}\""
}

# ── Intro ─────────────────────────────────────────────────────────────
printf "\n"
printf "${CYAN}┌${NC}  ${BOLD}Forged${NC} ${DIM}— self-improving browser automation${NC}\n"
printf "${BAR}\n"
printf "${BAR}  Set up the MCP server for Claude Code, Cursor, or Windsurf.\n"
printf "${BAR}  Your AI assistant learns from every browser task and gets faster.\n"

# ── Step 1: Prerequisites ────────────────────────────────────────────
step_start "Checking prerequisites"

# Python 3.11+
if ! command -v python3 &>/dev/null && ! command -v python &>/dev/null; then
    step_fail "Python 3.11+ is required. Install: https://python.org/downloads"
fi

PYTHON=$(command -v python3 || command -v python)
PY_VERSION=$("$PYTHON" -c 'import sys; print(f"{sys.version_info.major}.{sys.version_info.minor}")')
PY_MAJOR=$("$PYTHON" -c 'import sys; print(sys.version_info.major)')
PY_MINOR=$("$PYTHON" -c 'import sys; print(sys.version_info.minor)')

if [ "$PY_MAJOR" -lt 3 ] || { [ "$PY_MAJOR" -eq 3 ] && [ "$PY_MINOR" -lt 11 ]; }; then
    step_fail "Python 3.11+ required (found $PY_VERSION)"
fi
step_ok "Python $PY_VERSION"

# Claude Code CLI
if ! command -v claude &>/dev/null; then
    step_fail "Claude Code CLI not found. Install: https://docs.anthropic.com/en/docs/claude-code"
fi
step_ok "Claude Code CLI"

# ── Step 2: Locate repo ──────────────────────────────────────────────
step_start "Locating Forged"

if [ -f "mcp_server.py" ] && [ -f "src/api.py" ]; then
    FORGED_DIR="$(pwd)"
    step_ok "Found in current directory"
    step_info "$FORGED_DIR"
else
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
        step_warn "Not found automatically"
        prompt_input "Path to Forged directory" "" FORGED_DIR
        FORGED_DIR="${FORGED_DIR/#\~/$HOME}"

        if [ ! -f "$FORGED_DIR/mcp_server.py" ]; then
            step_fail "mcp_server.py not found in $FORGED_DIR"
        fi
    fi
    step_ok "Found Forged"
    step_info "$FORGED_DIR"
fi

MCP_SERVER_PATH="$FORGED_DIR/mcp_server.py"

# ── Step 3: Dependencies ─────────────────────────────────────────────
step_start "Dependencies"

MISSING_DEPS=()
"$PYTHON" -c "import mcp" 2>/dev/null || MISSING_DEPS+=("mcp")
"$PYTHON" -c "import httpx" 2>/dev/null || MISSING_DEPS+=("httpx")

if [ ${#MISSING_DEPS[@]} -gt 0 ]; then
    step_warn "Missing: ${MISSING_DEPS[*]}"
    prompt_confirm "Install now?" INSTALL_DEPS
    if [[ "$INSTALL_DEPS" =~ ^[Yy] ]]; then
        "$PYTHON" -m pip install "${MISSING_DEPS[@]}" --quiet &
        spinner $! "Installing ${MISSING_DEPS[*]}"
        wait $! 2>/dev/null
        step_ok "Installed ${MISSING_DEPS[*]}"
    else
        step_fail "Cannot continue without: ${MISSING_DEPS[*]}"
    fi
else
    step_ok "mcp, httpx"
fi

# ── Step 4: Backend URL ──────────────────────────────────────────────
step_start "Backend"

DEFAULT_URL="http://localhost:8000"
prompt_input "Forged backend URL" "$DEFAULT_URL" BACKEND_URL

# Health check
if command -v curl &>/dev/null; then
    if curl -s --max-time 2 "$BACKEND_URL/api/health" &>/dev/null; then
        step_ok "Backend reachable at $BACKEND_URL"
    else
        step_warn "Not reachable yet (start it before using Forged)"
    fi
fi

# ── Step 5: Scope ────────────────────────────────────────────────────
step_start "Registration scope"

prompt_select \
    "Where should Forged be available?" \
    "All sessions (user scope)" \
    "This project only (project scope)" \
    "1" \
    SCOPE_CHOICE

case "$SCOPE_CHOICE" in
    2) SCOPE="project" ;;
    *) SCOPE="user" ;;
esac
step_ok "Using $SCOPE scope"

# ── Step 6: Register ─────────────────────────────────────────────────
step_start "Registering with Claude Code"

# Remove old registration silently
claude mcp remove forged -s "$SCOPE" 2>/dev/null || true

# Register
{
    claude mcp add \
        -s "$SCOPE" \
        -e "FORGED_API_URL=${BACKEND_URL}" \
        forged \
        -- \
        "$PYTHON" "$MCP_SERVER_PATH"
} &>/dev/null &
spinner $! "Registering MCP server"
wait $! 2>/dev/null

# Verify
if claude mcp get forged -s "$SCOPE" &>/dev/null; then
    step_ok "Registered and verified"
else
    step_warn "Registered (could not verify — try: claude mcp list)"
fi

# ── Outro ─────────────────────────────────────────────────────────────
step_end
printf "${GREEN}◆${NC}  ${BOLD}${GREEN}Setup complete!${NC}\n"
printf "${BAR}\n"
printf "${BAR}  ${BOLD}Next steps:${NC}\n"
printf "${BAR}\n"
printf "${BAR}  ${DIM}1.${NC} Start the backend:\n"
printf "${BAR}     ${CYAN}cd \"$FORGED_DIR\" && ./dev.sh${NC}\n"
printf "${BAR}\n"
printf "${BAR}  ${DIM}2.${NC} Restart Claude Code ${DIM}(or open a new session)${NC}\n"
printf "${BAR}\n"
printf "${BAR}  ${DIM}3.${NC} Ask your AI assistant:\n"
printf "${BAR}     ${ITALIC}\"Go to news.ycombinator.com and get the top story\"${NC}\n"
printf "${BAR}\n"
printf "${BAR}  Run it again — it gets ${BOLD}faster${NC} every time.\n"
printf "${BAR}\n"
printf "${BAR}  ${DIM}Manage:  claude mcp list · claude mcp get forged · claude mcp remove forged${NC}\n"
printf "${DIM}└${NC}\n\n"
