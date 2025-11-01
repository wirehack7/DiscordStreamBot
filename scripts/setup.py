#!/usr/bin/env python3
"""
Discord Stream Bot - Setup Script
Simple setup utility for development environment.
"""

import os
import sys
import subprocess
import argparse


def install_dependencies():
    """Install Python dependencies."""
    print("Installing dependencies...")
    try:
        subprocess.run(
            [sys.executable, "-m", "pip", "install", "-r", "requirements.txt"],
            check=True,
        )
        print("✓ Dependencies installed successfully")
    except subprocess.CalledProcessError:
        print("✗ Failed to install dependencies")
        return False
    return True


def setup_config():
    """Set up configuration file."""
    config_template = "config/config.ini.dist"
    config_file = "config.ini"

    if os.path.exists(config_file):
        print(f"✓ Configuration file already exists: {config_file}")
        return True

    if os.path.exists(config_template):
        import shutil

        shutil.copy(config_template, config_file)
        print(f"✓ Configuration template copied to {config_file}")
        print("⚠ Please edit config.ini with your Discord and Twitch credentials")
        return True
    else:
        print(f"✗ Configuration template not found: {config_template}")
        return False


def create_directories():
    """Create necessary directories."""
    dirs = ["data/logs", "data/server_log", "data/images"]
    for dir_path in dirs:
        os.makedirs(dir_path, exist_ok=True)
        print(f"✓ Created directory: {dir_path}")


def run_bot():
    """Run the bot."""
    if not os.path.exists("config.ini"):
        print("✗ config.ini not found. Run setup first.")
        return False

    try:
        subprocess.run([sys.executable, "src/main.py"], check=True)
    except KeyboardInterrupt:
        print("\n✓ Bot stopped by user")
    except subprocess.CalledProcessError:
        print("✗ Bot failed to start")
        return False
    return True


def show_status():
    """Show bot status."""
    print("Discord Stream Bot Status:")
    print(f"✓ Python: {sys.version}")
    print(f"✓ Working directory: {os.getcwd()}")

    # Check files
    files_to_check = ["src/main.py", "src/func/discordbot.py", "config.ini"]
    for file_path in files_to_check:
        if os.path.exists(file_path):
            print(f"✓ Found: {file_path}")
        else:
            print(f"✗ Missing: {file_path}")


def clean():
    """Clean up environment."""
    import shutil

    # Clean data directories but keep structure
    data_dirs = ["data/logs", "data/server_log", "data/images"]
    for dir_path in data_dirs:
        if os.path.exists(dir_path):
            for file in os.listdir(dir_path):
                file_path = os.path.join(dir_path, file)
                if os.path.isfile(file_path):
                    os.remove(file_path)
            print(f"✓ Cleaned: {dir_path}")

    print("✓ Environment cleaned")


def main():
    parser = argparse.ArgumentParser(description="Discord Stream Bot Setup")
    parser.add_argument(
        "command",
        nargs="?",
        default="help",
        choices=["install", "run", "status", "clean", "help"],
        help="Command to execute",
    )

    args = parser.parse_args()

    if args.command == "install":
        create_directories()
        if install_dependencies():
            setup_config()
            print("\n✓ Setup complete! Edit config.ini and run 'python src/main.py'")
    elif args.command == "run":
        run_bot()
    elif args.command == "status":
        show_status()
    elif args.command == "clean":
        clean()
    else:
        print("Discord Stream Bot Setup")
        print("\nCommands:")
        print("  install  - Set up development environment")
        print("  run      - Run the bot")
        print("  status   - Show status")
        print("  clean    - Clean up environment")


if __name__ == "__main__":
    main()
