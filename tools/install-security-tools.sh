#!/usr/bin/env bash
# install-security-tools.sh — Tiered installation of external security tools for HexStrike AI
# Usage: sudo ./tools/install-security-tools.sh
# Idempotent: safe to re-run, skips already-installed tools

set -euo pipefail

# Colors
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
CYAN='\033[0;36m'
NC='\033[0m'

INSTALLED=0
SKIPPED=0
FAILED=0
FAILED_LIST=()

log_info()  { echo -e "${CYAN}[INFO]${NC} $1"; }
log_ok()    { echo -e "${GREEN}[OK]${NC} $1"; }
log_skip()  { echo -e "${YELLOW}[SKIP]${NC} $1 (already installed)"; }
log_fail()  { echo -e "${RED}[FAIL]${NC} $1"; }

check_root() {
    if [[ $EUID -ne 0 ]]; then
        echo -e "${RED}This script must be run as root (sudo)${NC}"
        exit 1
    fi
}

# Check if a command exists
has() { command -v "$1" &>/dev/null; }

# Install via apt if not present
apt_install() {
    local pkg="$1"
    local cmd="${2:-$1}"
    if has "$cmd"; then
        log_skip "$pkg"
        ((SKIPPED++))
    else
        log_info "Installing $pkg..."
        if apt-get install -y -qq "$pkg" &>/dev/null; then
            log_ok "$pkg installed"
            ((INSTALLED++))
        else
            log_fail "$pkg"
            ((FAILED++))
            FAILED_LIST+=("$pkg")
        fi
    fi
}

# Install Go tool if not present
go_install() {
    local name="$1"
    local pkg="$2"
    local cmd="${3:-$name}"
    if has "$cmd"; then
        log_skip "$name"
        ((SKIPPED++))
    else
        log_info "Installing $name via go install..."
        if GOPATH=/usr/local/go-tools go install "$pkg" &>/dev/null; then
            # Symlink to /usr/local/bin
            local bin="/usr/local/go-tools/bin/$cmd"
            if [[ -f "$bin" ]]; then
                ln -sf "$bin" "/usr/local/bin/$cmd"
            fi
            log_ok "$name installed"
            ((INSTALLED++))
        else
            log_fail "$name"
            ((FAILED++))
            FAILED_LIST+=("$name")
        fi
    fi
}

# Install Python tool via pipx if not present
pipx_install() {
    local name="$1"
    local pkg="${2:-$1}"
    local cmd="${3:-$1}"
    if has "$cmd"; then
        log_skip "$name"
        ((SKIPPED++))
    else
        log_info "Installing $name via pipx..."
        if pipx install "$pkg" &>/dev/null; then
            log_ok "$name installed"
            ((INSTALLED++))
        else
            log_fail "$name"
            ((FAILED++))
            FAILED_LIST+=("$name")
        fi
    fi
}

echo ""
echo -e "${CYAN}╔══════════════════════════════════════════════════════════════╗${NC}"
echo -e "${CYAN}║  HexStrike AI — Security Tools Installer                   ║${NC}"
echo -e "${CYAN}║  Tiered installation for AI-Defender offensive capabilities ║${NC}"
echo -e "${CYAN}╚══════════════════════════════════════════════════════════════╝${NC}"
echo ""

check_root

# ──────────────────────────────────────────────────────────────
# Prerequisites
# ──────────────────────────────────────────────────────────────
log_info "Updating apt package index..."
apt-get update -qq &>/dev/null

# Ensure pipx is available
if ! has pipx; then
    log_info "Installing pipx..."
    apt-get install -y -qq pipx &>/dev/null
    pipx ensurepath &>/dev/null || true
fi

# Ensure Go is available (needed for Tier 2)
if ! has go; then
    log_info "Installing Go toolchain..."
    apt-get install -y -qq golang-go &>/dev/null || {
        # Fallback: install from official tarball
        GO_VERSION="1.22.5"
        wget -q "https://go.dev/dl/go${GO_VERSION}.linux-amd64.tar.gz" -O /tmp/go.tar.gz
        rm -rf /usr/local/go
        tar -C /usr/local -xzf /tmp/go.tar.gz
        rm /tmp/go.tar.gz
        ln -sf /usr/local/go/bin/go /usr/local/bin/go
        ln -sf /usr/local/go/bin/gofmt /usr/local/bin/gofmt
    }
fi

mkdir -p /usr/local/go-tools

# ──────────────────────────────────────────────────────────────
# Tier 1 — Essential (apt-get)
# ──────────────────────────────────────────────────────────────
echo ""
echo -e "${CYAN}── Tier 1: Essential tools (apt) ──${NC}"

apt_install nmap
apt_install masscan
apt_install hydra
apt_install john
apt_install hashcat
apt_install sqlmap
apt_install nikto
apt_install dirb
apt_install gobuster
apt_install enum4linux
apt_install smbclient
apt_install netcat-openbsd nc
apt_install curl
apt_install whois
apt_install dnsutils dig
apt_install tcpdump
apt_install wireshark tshark
apt_install nbtscan
apt_install arp-scan
apt_install binwalk
apt_install foremost
apt_install exiftool
apt_install steghide
apt_install testdisk
apt_install gdb
apt_install radare2 r2

# ──────────────────────────────────────────────────────────────
# Tier 2 — Go tools (go install)
# ──────────────────────────────────────────────────────────────
echo ""
echo -e "${CYAN}── Tier 2: Go-based tools ──${NC}"

go_install nuclei    "github.com/projectdiscovery/nuclei/v3/cmd/nuclei@latest"
go_install subfinder "github.com/projectdiscovery/subfinder/v2/cmd/subfinder@latest"
go_install httpx     "github.com/projectdiscovery/httpx/cmd/httpx@latest"
go_install katana    "github.com/projectdiscovery/katana/cmd/katana@latest"
go_install ffuf      "github.com/ffuf/ffuf/v2@latest"
go_install feroxbuster "github.com/epi052/feroxbuster@latest" feroxbuster || true
go_install amass     "github.com/owasp-amass/amass/v4/...@latest"
go_install hakrawler "github.com/hakluke/hakrawler@latest"
go_install gau       "github.com/lc/gau/v2/cmd/gau@latest"
go_install waybackurls "github.com/tomnomnom/waybackurls@latest"
go_install anew      "github.com/tomnomnom/anew@latest"
go_install qsreplace "github.com/tomnomnom/qsreplace@latest"

# ──────────────────────────────────────────────────────────────
# Tier 3 — Python tools (pipx)
# ──────────────────────────────────────────────────────────────
echo ""
echo -e "${CYAN}── Tier 3: Python-based tools ──${NC}"

pipx_install dirsearch
pipx_install wpscan
pipx_install theharvester theHarvester theHarvester
pipx_install sherlock sherlock-project sherlock
pipx_install arjun

# ──────────────────────────────────────────────────────────────
# Tier 4 — Specialized
# ──────────────────────────────────────────────────────────────
echo ""
echo -e "${CYAN}── Tier 4: Specialized tools ──${NC}"

# RustScan (cargo or apt)
if has rustscan; then
    log_skip "rustscan"
    ((SKIPPED++))
else
    if has cargo; then
        log_info "Installing rustscan via cargo..."
        if cargo install rustscan &>/dev/null; then
            log_ok "rustscan installed"
            ((INSTALLED++))
        else
            log_fail "rustscan (cargo)"
            ((FAILED++))
            FAILED_LIST+=("rustscan")
        fi
    else
        log_fail "rustscan (cargo not available, install Rust toolchain first)"
        ((FAILED++))
        FAILED_LIST+=("rustscan")
    fi
fi

# wafw00f
pipx_install wafw00f

# dnsenum
apt_install dnsenum

# fierce
pipx_install fierce

# ──────────────────────────────────────────────────────────────
# Summary
# ──────────────────────────────────────────────────────────────
echo ""
echo -e "${CYAN}══════════════════════════════════════════════════════════════${NC}"
echo -e "${GREEN}  Installed: $INSTALLED${NC}"
echo -e "${YELLOW}  Skipped:   $SKIPPED${NC}"
echo -e "${RED}  Failed:    $FAILED${NC}"
if [[ ${#FAILED_LIST[@]} -gt 0 ]]; then
    echo -e "${RED}  Failed tools: ${FAILED_LIST[*]}${NC}"
fi
echo -e "${CYAN}══════════════════════════════════════════════════════════════${NC}"
echo ""

# Verification of core tools
echo -e "${CYAN}── Verification ──${NC}"
for tool in nmap sqlmap nuclei; do
    if has "$tool"; then
        echo -e "${GREEN}  ✓ $tool$(NC) — $($tool --version 2>&1 | head -1)"
    else
        echo -e "${RED}  ✗ $tool — not found${NC}"
    fi
done
echo ""
