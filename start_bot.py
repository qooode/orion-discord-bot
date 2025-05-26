#!/usr/bin/env python3
"""
Orion Bot Startup Script
Simple script to start the Orion Discord Bot with dependency checking
"""

import os
import sys
import subprocess

def check_python_version():
    """Check if Python version is 3.8+"""
    if sys.version_info < (3, 8):
        print("❌ Python 3.8+ required. You have:", sys.version)
        return False
    print(f"✅ Python {sys.version.split()[0]} - OK")
    return True

def check_dependencies():
    """Check if required packages are installed"""
    required_packages = ['discord', 'dotenv']
    missing_packages = []
    
    for package in required_packages:
        try:
            __import__(package)
            print(f"✅ {package} - OK")
        except ImportError:
            missing_packages.append(package)
            print(f"❌ {package} - MISSING")
    
    if missing_packages:
        print(f"\n🔧 Installing missing packages: {', '.join(missing_packages)}")
        try:
            if 'discord' in missing_packages:
                subprocess.check_call([sys.executable, '-m', 'pip', 'install', 'discord.py'])
            if 'dotenv' in missing_packages:
                subprocess.check_call([sys.executable, '-m', 'pip', 'install', 'python-dotenv'])
            print("✅ Dependencies installed!")
            return True
        except subprocess.CalledProcessError:
            print("❌ Failed to install dependencies. Please run manually:")
            print("pip3 install -r requirements.txt")
            print("OR:")
            print("pip3 install discord.py python-dotenv")
            return False
    
    return True

def check_env_file():
    """Check if bot.env exists and has required variables"""
    if not os.path.exists('bot.env'):
        print("❌ bot.env file not found!")
        print("\n🔧 Creating sample bot.env file...")
        with open('bot.env', 'w') as f:
            f.write("DISCORD_TOKEN=your_bot_token_here\n")
            f.write("COMMAND_PREFIX=!\n")
        print("✅ Created bot.env - Please edit it with your bot token")
        return False
    
    # Check if token is set
    with open('bot.env', 'r') as f:
        content = f.read()
        if 'your_bot_token_here' in content:
            print("❌ Please edit bot.env with your actual bot token")
            return False
        if 'DISCORD_TOKEN=' not in content:
            print("❌ DISCORD_TOKEN not found in bot.env")
            return False
    
    print("✅ bot.env - OK")
    return True

def check_main_file():
    """Check if main.py exists"""
    if not os.path.exists('main.py'):
        print("❌ main.py not found! Make sure you're in the right directory.")
        return False
    print("✅ main.py - OK")
    return True

def main():
    """Main startup function"""
    print("🤖 === ORION BOT STARTUP CHECKER ===\n")
    
    # Run all checks
    checks = [
        ("Python Version", check_python_version),
        ("Dependencies", check_dependencies), 
        ("Environment File", check_env_file),
        ("Main Script", check_main_file)
    ]
    
    all_passed = True
    for check_name, check_func in checks:
        print(f"🔍 Checking {check_name}...")
        if not check_func():
            all_passed = False
        print()
    
    if not all_passed:
        print("❌ Some checks failed. Please fix the issues above and try again.")
        return
    
    print("🎉 All checks passed! Starting bot...\n")
    print("=" * 50)
    
    # Start the bot
    try:
        import main
        main.main()
    except KeyboardInterrupt:
        print("\n👋 Bot stopped by user")
    except Exception as e:
        print(f"\n❌ Error starting bot: {e}")
        print("Check the error above and your bot.env file")

if __name__ == "__main__":
    main() 