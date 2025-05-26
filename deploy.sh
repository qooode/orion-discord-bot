#!/bin/bash

# Orion Discord Bot - Production Deployment Script
# This script automates the complete setup process

set -e  # Exit on any error

echo "🤖 === ORION BOT DEPLOYMENT SCRIPT ==="
echo "This will set up Orion Bot for production use"
echo

# Check if running as root
if [ "$EUID" -eq 0 ]; then
    echo "❌ Please don't run this script as root"
    exit 1
fi

# Function to check if command exists
command_exists() {
    command -v "$1" >/dev/null 2>&1
}

# Check required tools
echo "🔍 Checking system requirements..."
if ! command_exists python3; then
    echo "❌ Python 3 is required but not installed"
    exit 1
fi

if ! command_exists git; then
    echo "❌ Git is required but not installed"
    exit 1
fi

echo "✅ System requirements OK"
echo

# Stop existing bot processes
echo "🛑 Stopping existing bot processes..."
pkill -f "python.*main.py" 2>/dev/null || true
pkill -f "python.*bot.py" 2>/dev/null || true
sleep 2
echo "✅ Existing processes stopped"
echo

# Setup directory
echo "📁 Setting up deployment directory..."
DEPLOY_DIR="orion-bot-$(date +%Y%m%d-%H%M%S)"
mkdir -p "$DEPLOY_DIR"
cd "$DEPLOY_DIR"

# Remove old deployment if exists
rm -rf orion-discord-bot 2>/dev/null || true
echo "✅ Directory prepared: $PWD"
echo

# Clone repository
echo "📦 Cloning Orion Bot repository..."
if ! git clone https://github.com/qooode/orion-discord-bot.git; then
    echo "❌ Failed to clone repository"
    exit 1
fi
cd orion-discord-bot
echo "✅ Repository cloned"
echo

# Create virtual environment
echo "🐍 Setting up Python virtual environment..."
python3 -m venv venv
source venv/bin/activate
echo "✅ Virtual environment created"
echo

# Install dependencies
echo "📦 Installing dependencies..."
if ! pip install -r requirements.txt; then
    echo "❌ Failed to install dependencies"
    exit 1
fi
echo "✅ Dependencies installed"
echo

# Check for existing bot.env
if [ -f "bot.env" ]; then
    echo "⚠️  bot.env already exists, backing up..."
    cp bot.env bot.env.backup
fi

# Create bot.env template
echo "🔑 Creating bot.env configuration file..."
cat > bot.env << 'EOF'
DISCORD_TOKEN=your_bot_token_here
COMMAND_PREFIX=!
EOF

echo "✅ bot.env created"
echo

# Instructions for user
echo "🎯 === NEXT STEPS ==="
echo "1. Edit the bot.env file with your Discord bot token:"
echo "   nano bot.env"
echo
echo "2. Replace 'your_bot_token_here' with your actual bot token"
echo
echo "3. Start the bot in background:"
echo "   source venv/bin/activate"
echo "   nohup python3 main.py > bot.log 2>&1 &"
echo
echo "4. Monitor the bot:"
echo "   tail -f bot.log"
echo "   ps aux | grep main.py"
echo
echo "📍 Bot installed in: $PWD"
echo

# Offer to open editor
read -p "🤔 Would you like to edit bot.env now? (y/n): " -n 1 -r
echo
if [[ $REPLY =~ ^[Yy]$ ]]; then
    if command_exists nano; then
        nano bot.env
    elif command_exists vim; then
        vim bot.env
    else
        echo "ℹ️  Please edit bot.env manually with your preferred editor"
    fi
fi

# Offer to start bot
read -p "🚀 Would you like to start the bot now? (y/n): " -n 1 -r
echo
if [[ $REPLY =~ ^[Yy]$ ]]; then
    # Check if token is configured
    if grep -q "your_bot_token_here" bot.env; then
        echo "❌ Please configure your bot token in bot.env first"
        exit 1
    fi
    
    echo "🚀 Starting bot in background..."
    source venv/bin/activate
    nohup python3 main.py > bot.log 2>&1 &
    echo "✅ Bot started! PID: $!"
    echo
    echo "📋 Useful commands:"
    echo "  tail -f bot.log           # View logs"
    echo "  ps aux | grep main.py     # Check if running"
    echo "  pkill -f 'python.*main.py'  # Stop bot"
    echo
fi

echo "🎉 Deployment complete!"
echo "📖 Read the README.md for more information" 