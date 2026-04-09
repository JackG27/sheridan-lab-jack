#!/bin/bash
# ═══════════════════════════════════════════════════════════════
#  sheridan-lab-jack Setup Script
#  Run this on your Linux machine to set everything up
# ═══════════════════════════════════════════════════════════════
set -e

GREEN='\033[0;32m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
NC='\033[0m'

echo "═══════════════════════════════════════════════════"
echo "  sheridan-lab-jack — Automated Setup"
echo "═══════════════════════════════════════════════════"

# ── Step 1: Check Docker ──
echo -e "\n${YELLOW}[1/6] Checking Docker...${NC}"
if command -v docker &> /dev/null; then
    echo -e "${GREEN}  ✓ Docker is installed$(docker --version)${NC}"
else
    echo -e "${RED}  ✗ Docker not found. Install it first:${NC}"
    echo "    curl -fsSL https://get.docker.com | sh"
    echo "    sudo usermod -aG docker \$USER"
    exit 1
fi

# ── Step 2: Install ContainerLab ──
echo -e "\n${YELLOW}[2/6] Checking ContainerLab...${NC}"
if command -v containerlab &> /dev/null; then
    echo -e "${GREEN}  ✓ ContainerLab is installed$(containerlab version | head -1)${NC}"
else
    echo "  Installing ContainerLab..."
    sudo bash -c "$(curl -sL https://get.containerlab.dev)"
    echo -e "${GREEN}  ✓ ContainerLab installed${NC}"
fi

# ── Step 3: Install system deps ──
echo -e "\n${YELLOW}[3/6] Installing sshpass...${NC}"
if command -v sshpass &> /dev/null; then
    echo -e "${GREEN}  ✓ sshpass already installed${NC}"
else
    sudo apt update -qq && sudo apt install -y sshpass
    echo -e "${GREEN}  ✓ sshpass installed${NC}"
fi

# ── Step 4: Install Python deps ──
echo -e "\n${YELLOW}[4/6] Installing Python dependencies...${NC}"
pip install -r requirements.txt --break-system-packages 2>/dev/null || pip install -r requirements.txt
echo -e "${GREEN}  ✓ Python dependencies installed${NC}"

# ── Step 5: Deploy the lab ──
echo -e "\n${YELLOW}[5/6] Deploying ContainerLab topology...${NC}"
sudo containerlab deploy --topo topology.yml --reconfigure 2>/dev/null || sudo containerlab deploy --topo topology.yml
echo -e "${GREEN}  ✓ Lab deployed${NC}"

# ── Step 6: Wait for SR Linux to boot ──
echo -e "\n${YELLOW}[6/6] Waiting for SR Linux to boot (this takes ~60 seconds)...${NC}"
for i in $(seq 1 12); do
    if sshpass -p 'NokiaSrl1!' ssh -o StrictHostKeyChecking=no -o ConnectTimeout=5 admin@clab-sheridan-lab-jack-srl -- "info from state /system information" &>/dev/null; then
        echo -e "${GREEN}  ✓ SR Linux is up and responding!${NC}"
        break
    fi
    if [ $i -eq 12 ]; then
        echo -e "${RED}  ✗ SR Linux didn't respond after 120s. Check: sudo docker logs clab-sheridan-lab-jack-srl${NC}"
        exit 1
    fi
    echo "  Waiting... ($((i*10))s)"
    sleep 10
done

echo ""
echo "═══════════════════════════════════════════════════"
echo -e "${GREEN}  Setup Complete!${NC}"
echo "═══════════════════════════════════════════════════"
echo ""
echo "  Next steps:"
echo "  1. Test tools:     python3 test_tools.py"
echo "  2. Start Claude:   claude"
echo "     Then ask:       'use get_device_info to check the router'"
echo ""
