#!/bin/bash

# Setup script for Sports Data Intelligence Platform

set -e

echo "🚀 Setting up Sports Data Intelligence Platform..."

# Colors
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
NC='\033[0m' # No Color

# Check Python
if ! command -v python3 &> /dev/null; then
    echo -e "${RED}Python 3 is required but not installed.${NC}"
    exit 1
fi
echo -e "${GREEN}✓ Python found${NC}"

# Check Node
if ! command -v node &> /dev/null; then
    echo -e "${RED}Node.js is required but not installed.${NC}"
    exit 1
fi
echo -e "${GREEN}✓ Node.js found${NC}"

# Setup backend
echo -e "\n${YELLOW}Setting up backend...${NC}"
cd backend

if [ ! -d "venv" ]; then
    python3 -m venv venv
fi

source venv/bin/activate
pip install --upgrade pip
pip install -r requirements.txt

# Copy env file if it doesn't exist
if [ ! -f ".env" ]; then
    cp .env.example .env
    echo -e "${YELLOW}⚠ Created .env file - please update with your API keys${NC}"
fi

echo -e "${GREEN}✓ Backend setup complete${NC}"

# Setup frontend
echo -e "\n${YELLOW}Setting up frontend...${NC}"
cd ../frontend
npm install

echo -e "${GREEN}✓ Frontend setup complete${NC}"

cd ..

echo -e "\n${GREEN}✅ Setup complete!${NC}"
echo ""
echo "Next steps:"
echo "1. Update backend/.env with your API keys"
echo "2. Start PostgreSQL and Redis"
echo "3. Run migrations: cd backend && alembic upgrade head"
echo "4. Start backend: python main.py"
echo "5. Start frontend: cd frontend && npm start"

