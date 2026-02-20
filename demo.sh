#!/usr/bin/env bash

# Color definitions
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
CYAN='\033[0;36m'
MAGENTA='\033[0;35m'
NC='\033[0m'

echo -e "\n${CYAN}blueprintx - Colorful Interface Demo${NC}\n"

echo "════════════════════════════════════════════════════════"
echo -e "${MAGENTA}BANNER:${NC}"
echo "════════════════════════════════════════════════════════"

cat << EOF
    ${MAGENTA}╔══════════════════════════════════════════════════════════╗${NC}
    ${MAGENTA}║${NC}                                                          ${MAGENTA}║${NC}
    ${MAGENTA}║${NC}          ${CYAN}██████╗ ██╗     ██╗   ██╗███████╗${MAGENTA}           ║${NC}
    ${MAGENTA}║${NC}          ${CYAN}██╔══██╗██║     ██║   ██║██╔════╝${MAGENTA}           ║${NC}
    ${MAGENTA}║${NC}          ${CYAN}██████╔╝██║     ██║   ██║█████╗  ${MAGENTA}           ║${NC}
    ${MAGENTA}║${NC}          ${CYAN}██╔══██╗██║     ██║   ██║██╔══╝  ${MAGENTA}           ║${NC}
    ${MAGENTA}║${NC}          ${CYAN}██████╔╝███████╗╚██████╔╝███████╗${MAGENTA}           ║${NC}
    ${MAGENTA}║${NC}          ${CYAN}╚═════╝ ╚══════╝ ╚═════╝ ╚══════╝${MAGENTA}           ║${NC}
    ${MAGENTA}║${NC}                                                          ${MAGENTA}║${NC}
    ${MAGENTA}║${NC}           ${GREEN}Project Scaffolding Made Simple${MAGENTA}            ║${NC}
    ${MAGENTA}║${NC}                                                          ${MAGENTA}║${NC}
    ${MAGENTA}╚══════════════════════════════════════════════════════════╝${NC}
EOF

echo
echo "════════════════════════════════════════════════════════"
echo -e "${MAGENTA}MENU OPTIONS WITH ICONS:${NC}"
echo "════════════════════════════════════════════════════════"
echo
echo -e "  ${GREEN}➜${NC} Create a project"
echo -e "  ${YELLOW}?${NC} Help (what can blueprintx do?)"
echo -e "  ${BLUE}▦${NC} Show scaffolding structures and examples"
echo -e "  ${RED}✕${NC} Cancel"
echo
echo "════════════════════════════════════════════════════════"
echo -e "${MAGENTA}STATUS MESSAGES:${NC}"
echo "════════════════════════════════════════════════════════"
echo
echo -e "${GREEN}[✓]${NC} Success message example"
echo -e "${RED}[✗]${NC} Error message example"
echo -e "${YELLOW}[!]${NC} Warning message example"
echo -e "${BLUE}[i]${NC} Info message example"
echo -e "${CYAN}[→]${NC} Config message example"
echo
echo "════════════════════════════════════════════════════════"
echo -e "${MAGENTA}SUCCESS BOX:${NC}"
echo "════════════════════════════════════════════════════════"
echo
echo -e "${GREEN}╔════════════════════════════════════════╗${NC}"
echo -e "${GREEN}║   ✓ Project created successfully!      ║${NC}"
echo -e "${GREEN}╚════════════════════════════════════════╝${NC}"
echo
echo -e "${CYAN}[→] Project: my-project${NC}"
echo -e "${CYAN}[→] Location: /home/user/my-project${NC}"
echo -e "${CYAN}[→] Skeleton: hex-service${NC}"
echo
