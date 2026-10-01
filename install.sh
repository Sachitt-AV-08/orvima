#!/usr/bin/env bash
# Orvima installer - installs Orvima CLI with MCP support
# Detects uv/pipx/pip and uses the best available installer

set -euo pipefail

# Colors
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
CYAN='\033[0;36m'
NC='\033[0m' # No Color

# Parse flags FIRST
FORCE=false
NO_MCP=false
POSITIONAL=()

while [[ $# -gt 0 ]]; do
    case $1 in
        --force) FORCE=true; shift ;;
        --no-mcp) NO_MCP=true; shift ;;
        -*) echo "Unknown option: $1"; exit 1 ;;
        *) POSITIONAL+=("$1"); shift ;;
    esac
done

# Now get version from positional args or default
VERSION="${POSITIONAL[0]:-latest}"

echo -e "${CYAN}╔══════════════════════════════════════════╗${NC}"
echo -e "${CYAN}║     Orvima Installer                     ║${NC}"
echo -e "${CYAN}║   The browser your AI drives             ║${NC}"
echo -e "${CYAN}╚══════════════════════════════════════════╝${NC}"
echo ""

# Get latest version if not specified
if [[ "$VERSION" == "latest" ]]; then
    echo -e "${YELLOW}Fetching latest release...${NC}"
    VERSION=$(curl -s https://api.github.com/repos/Sachitt-AV-08/orvima/releases/latest 2>/dev/null | grep '"tag_name"' | sed -E 's/.*"([^"]+)".*/\1/') || true
    if [[ -z "$VERSION" ]]; then
        echo -e "${RED}Failed to fetch latest release, using v0.1.0${NC}"
        VERSION="v0.1.0"
    fi
fi

echo -e "${CYAN}Target version: ${VERSION}${NC}"
echo ""

# Detect installer
if command -v uv &> /dev/null; then
    echo -e "${GREEN}Found uv - using uv tool install${NC}"
    if [[ "$NO_MCP" == true ]]; then
        uv tool install "orvima @ git+https://github.com/Sachitt-AV-08/orvima.git@${VERSION}"
    else
        uv tool install "orvima[mcp] @ git+https://github.com/Sachitt-AV-08/orvima.git@${VERSION}"
    fi
elif command -v pipx &> /dev/null; then
    echo -e "${GREEN}Found pipx - using pipx install${NC}"
    if [[ "$NO_MCP" == true ]]; then
        pipx install "orvima @ git+https://github.com/Sachitt-AV-08/orvima.git@${VERSION}"
    else
        pipx install "orvima[mcp] @ git+https://github.com/Sachitt-AV-08/orvima.git@${VERSION}"
    fi
elif command -v pip &> /dev/null; then
    echo -e "${GREEN}Found pip - using pip install${NC}"
    if [[ "$VERSION" == "latest" ]]; then
        echo -e "${YELLOW}Using git install for latest...${NC}"
        pip install "orvima[mcp]@git+https://github.com/Sachitt-AV-08/orvima.git"
    else
        WHEEL_URL="https://github.com/Sachitt-AV-08/orvima/releases/download/${VERSION}/orvima-${VERSION#v}-py3-none-any.whl"
        if [[ "$NO_MCP" == true ]]; then
            pip install "$WHEEL_URL"
        else
            pip install "orvima[mcp] @ $WHEEL_URL"
        fi
    fi
else
    echo -e "${RED}No installer found (uv/pipx/pip). Please install Python first.${NC}"
    exit 1
fi

echo ""
echo -e "${GREEN}✓ Orvima installed successfully!${NC}"
echo ""
echo -e "${CYAN}Quick start:${NC}"
echo "  orvima demo                    # Offline tour"
echo "  orvima serve --mode real       # Launch API + UI at :8301"
echo "  orvima run \"your goal\"         # Headless agent"
echo ""
echo -e "${CYAN}MCP config (Claude Desktop / Cursor / Copilot):${NC}"
cat << 'EOF'
{
  "mcpServers": {
    "orvima": { "command": "orvima", "args": ["mcp", "--mode", "demo"], "type": "stdio" }
  }
}
EOF