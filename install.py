#!/usr/bin/env python3
"""
Installation script for the Phytoextraction Research Data Extractor
Automates the setup process
"""

import os
import sys
import subprocess
import shutil
from pathlib import Path

def run_command(command, description, optional=False):
    """Run a command and handle errors"""
    try:
        print(f"📦 {description}...")
        result = subprocess.run(command, shell=True, check=True, capture_output=True, text=True)
        print(f"✅ {description} completed")
        return True
    except subprocess.CalledProcessError as e:
        if optional:
            print(f"⚠️  {description} failed (optional): {e}")
            return False
        else:
            print(f"❌ {description} failed: {e}")
            if e.stdout:
                print(f"Output: {e.stdout}")
            if e.stderr:
                print(f"Error: {e.stderr}")
            return False

def check_prerequisites():
    """Check system prerequisites"""
    print("🔍 Checking prerequisites...")
    
    # Check Python version
    if sys.version_info < (3, 8):
        print("❌ Python 3.8 or higher is required")
        return False
    
    # Check pip
    if not shutil.which('pip'):
        print("❌ pip is not available")
        return False
    
    print("✅ Prerequisites check passed")
    return True

def install_requirements():
    """Install Python requirements"""
    if not os.path.exists('requirements.txt'):
        print("❌ requirements.txt not found")
        return False
    
    return run_command(
        f"{sys.executable} -m pip install -r requirements.txt",
        "Installing Python requirements"
    )

def install_optional_dependencies():
    """Install optional dependencies"""
    print("\n🔧 Installing optional dependencies...")
    
    # Nougat OCR
    nougat_success = run_command(
        f"{sys.executable} -m pip install nougat-ocr",
        "Installing Nougat OCR",
        optional=True
    )
    
    if not nougat_success:
        print("   Note: Nougat OCR requires additional system dependencies")
        print("   See: https://github.com/facebookresearch/nougat for details")
    
    return True

def setup_configuration():
    """Set up configuration files"""
    print("\n⚙️  Setting up configuration...")
    
    if not os.path.exists('.env') and os.path.exists('config.env.example'):
        shutil.copy('config.env.example', '.env')
        print("✅ Created .env file from template")
        print("📝 Please edit .env file with your specific configuration")
        return True
    elif os.path.exists('.env'):
        print("✅ Configuration file already exists")
        return True
    else:
        print("⚠️  No configuration template found")
        return False

def create_directories():
    """Create necessary directories"""
    print("\n📁 Creating directory structure...")
    
    directories = [
        'temp',
        'uploads', 
        'outputs',
        'logs'
    ]
    
    for directory in directories:
        Path(directory).mkdir(exist_ok=True)
    
    print("✅ Directory structure created")

def check_mongodb():
    """Check if MongoDB is available"""
    print("\n🗄️  Checking MongoDB...")
    
    # Check if MongoDB is running locally
    try:
        import pymongo
        client = pymongo.MongoClient('mongodb://localhost:27017/', serverSelectionTimeoutMS=2000)
        client.admin.command('ping')
        print("✅ MongoDB is running locally")
        return True
    except:
        print("⚠️  MongoDB not found locally")
        print("   Options:")
        print("   1. Install MongoDB locally: https://docs.mongodb.com/manual/installation/")
        print("   2. Use MongoDB Atlas (cloud): https://www.mongodb.com/atlas")
        print("   3. Update MONGODB_URL in .env file for remote instance")
        return False

def print_next_steps():
    """Print instructions for next steps"""
    print("\n" + "="*60)
    print("🎉 Installation completed!")
    print("="*60)
    print("\n📝 Next Steps:")
    print("1. Edit .env file with your API keys and configuration")
    print("2. Ensure MongoDB is running (local or cloud)")
    print("3. Run the application:")
    print("   python start.py")
    print("\n🔧 Optional Setup:")
    print("• LM Studio: Download from https://lmstudio.ai/")
    print("• Ollama: Install from https://ollama.ai/")
    print("• API Keys: OpenAI, Gemini for cloud processing")
    print("\n📚 Documentation:")
    print("• README.md - Complete setup and usage guide")
    print("• http://localhost:8000/docs - API documentation (after starting)")
    print("\n" + "="*60)

def main():
    """Main installation function"""
    print("🧬 Phytoextraction Research Data Extractor - Installation")
    print("="*60)
    
    # Check prerequisites
    if not check_prerequisites():
        sys.exit(1)
    
    # Install Python requirements
    if not install_requirements():
        print("❌ Failed to install requirements")
        sys.exit(1)
    
    # Install optional dependencies
    install_optional_dependencies()
    
    # Setup configuration
    setup_configuration()
    
    # Create directories
    create_directories()
    
    # Check MongoDB
    check_mongodb()
    
    # Print next steps
    print_next_steps()

if __name__ == "__main__":
    main()
