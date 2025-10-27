#!/bin/bash

# Quick Start Script for Sports Betting Platform
# This script sets up the environment and starts all services

echo "=========================================="
echo "Sports Betting Platform - Quick Start"
echo "=========================================="
echo ""

# Check if Docker is running
if ! docker info > /dev/null 2>&1; then
    echo "❌ Docker is not running. Please start Docker first."
    exit 1
fi

echo "✅ Docker is running"
echo ""

# Check if .env file exists
if [ ! -f "backend/.env" ]; then
    echo "⚠️  No .env file found. Creating from example..."
    cp .env.example backend/.env
    echo "✅ Created backend/.env file"
else
    echo "✅ .env file exists"
fi

echo ""
echo "Starting services with Docker Compose..."
echo ""

# Start services
docker-compose up -d postgres redis

echo ""
echo "⏳ Waiting for services to be healthy..."
sleep 5

# Check service health
echo ""
echo "Service Status:"
docker-compose ps

echo ""
echo "=========================================="
echo "✅ Services Started!"
echo "=========================================="
echo ""
echo "Next steps:"
echo ""
echo "1. Start the backend:"
echo "   cd backend"
echo "   python main.py"
echo ""
echo "2. In another terminal, start the frontend:"
echo "   cd frontend"
echo "   npm install"
echo "   npm run dev"
echo ""
echo "3. Access the application:"
echo "   Frontend: http://localhost:3000"
echo "   Backend API: http://localhost:8000"
echo "   API Docs: http://localhost:8000/docs"
echo ""
echo "📚 For API keys setup, see: SETUP_API_KEYS.md"
echo ""
