#!/usr/bin/env python3
"""
Arable Atlas - Quick Setup Script
Automates dependency installation, environment file configuration, and directory setup.
"""

import os
import sys
import subprocess
import shutil

def print_banner():
    print("============================================================")
    print(" 🌱  ARABLE ATLAS - QUICK SETUP & INITIALIZATION")
    print("============================================================")

def check_python_version():
    print("[1/4] Checking Python version...")
    if sys.version_info < (3, 8):
        print("❌ Error: Python 3.8 or higher is required. Found Python", sys.version)
        sys.exit(1)
    print(f"✅ Python version {sys.version.split()[0]} is compatible.")

def install_dependencies():
    print("\n[2/4] Installing Python dependencies from 'req.txt'...")
    req_file = "req.txt"
    if not os.path.exists(req_file):
        print(f"❌ Error: Requirement file '{req_file}' not found.")
        sys.exit(1)
    
    try:
        subprocess.check_call([sys.executable, "-m", "pip", "install", "-r", req_file])
        print("✅ Dependencies installed successfully.")
    except subprocess.CalledProcessError as e:
        print(f"❌ Error installing dependencies: {e}")
        sys.exit(1)

def setup_environment():
    print("\n[3/4] Configuring environment (.env)...")
    env_file = ".env"
    env_example = ".env.example"
    
    if os.path.exists(env_file):
        print("ℹ️  Existing '.env' file found. Skipping creation.")
    elif os.path.exists(env_example):
        shutil.copy(env_example, env_file)
        print("✅ Created '.env' from '.env.example'. Please update it with your API keys!")
    else:
        print("⚠️ Warning: '.env.example' not found. Creating a blank '.env' file.")
        with open(env_file, "w") as f:
            f.write("GEMINI_API_KEY=your_gemini_api_key_here\n")
            f.write("OPENWEATHER_API_KEY=your_openweather_api_key_here\n")
            f.write("DATABASE_URL=sqlite:///agrimap.db\n")
            f.write("SECRET_KEY=super_secret_key_here\n")

def setup_directories():
    print("\n[4/4] Setting up required project directories...")
    upload_folder = "uploads"
    if not os.path.exists(upload_folder):
        os.makedirs(upload_folder)
        print(f"✅ Created '{upload_folder}' directory.")
    else:
        print(f"ℹ️  Directory '{upload_folder}' already exists.")

def main():
    print_banner()
    check_python_version()
    install_dependencies()
    setup_environment()
    setup_directories()
    
    print("\n============================================================")
    print(" 🎉 SETUP COMPLETE! Arable Atlas & Plotty 🌱 are ready.")
    print("============================================================")
    print(" Next steps:")
    print(" 1. Edit your .env file and add your GEMINI_API_KEY and OPENWEATHER_API_KEY")
    print(" 2. Run the application:")
    print("    python app.py          (Development mode)")
    print("    python run_production.py (Production mode)")
    print("============================================================")

if __name__ == "__main__":
    main()
