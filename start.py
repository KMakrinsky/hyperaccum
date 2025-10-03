#!/usr/bin/env python3
"""
Startup script for the Phytoextraction Research Data Extractor
Handles initialization, dependency checking, and server startup
"""

import os
import sys
import subprocess
import importlib.util
from pathlib import Path

def check_python_version():
    """Check if Python version is compatible"""
    if sys.version_info < (3, 8):
        print("❌ Error: Python 3.8 or higher is required")
        print(f"Current version: {sys.version}")
        sys.exit(1)
    print(f"✅ Python version: {sys.version.split()[0]}")

def check_dependencies():
    """Check if required dependencies are installed"""
    required_packages = [
        'fastapi',
        'uvicorn',
        'pymongo',
        'PyPDF2',
        'fitz',  # PyMuPDF
        'openai',
        'requests'
    ]
    
    missing_packages = []
    
    for package in required_packages:
        spec = importlib.util.find_spec(package)
        if spec is None:
            missing_packages.append(package)
        else:
            print(f"✅ {package}")
    
    if missing_packages:
        print(f"\n❌ Missing packages: {', '.join(missing_packages)}")
        print("Install with: pip install -r requirements.txt")
        return False
    
    return True

def check_optional_dependencies():
    """Check optional dependencies and provide setup instructions"""
    optional_deps = {
        'nougat': {
            'import_name': 'nougat',
            'install_cmd': 'pip install nougat-ocr',
            'description': 'Advanced PDF OCR processing'
        }
    }
    
    print("\n📋 Optional Dependencies:")
    for name, info in optional_deps.items():
        spec = importlib.util.find_spec(info['import_name'])
        if spec is None:
            print(f"⚠️  {name}: Not installed - {info['description']}")
            print(f"   Install with: {info['install_cmd']}")
        else:
            print(f"✅ {name}: Available")

def check_config_file():
    """Check if configuration file exists"""
    if not os.path.exists('.env'):
        if os.path.exists('config.env.example'):
            print("\n⚠️  No .env file found. Copy config.env.example to .env and configure:")
            print("   cp config.env.example .env")
            print("   # Then edit .env with your settings")
        else:
            print("\n⚠️  No configuration file found.")
        return False
    else:
        print("✅ Configuration file found")
        return True

def check_mongodb_connection():
    """Test MongoDB connection"""
    try:
        from pymongo import MongoClient
        import os
        from dotenv import load_dotenv
        
        load_dotenv()
        
        mongodb_url = os.getenv('MONGODB_URL', 'mongodb://localhost:27017/')
        client = MongoClient(mongodb_url, serverSelectionTimeoutMS=2000)
        client.admin.command('ping')
        print("✅ MongoDB connection successful")
        return True
    except Exception as e:
        print(f"⚠️  MongoDB connection failed: {e}")
        print("   Make sure MongoDB is running or check your MONGODB_URL")
        return False

def create_directory_structure():
    """Create necessary directories"""
    directories = [
        'temp',
        'uploads',
        'outputs'
    ]
    
    for directory in directories:
        Path(directory).mkdir(exist_ok=True)
    
    print("✅ Directory structure created")

def main():
    """Main startup function"""
    print("🧬 Phytoextraction Research Data Extractor")
    print("=" * 50)
    
    # System checks
    print("\n🔍 System Checks:")
    check_python_version()
    
    print("\n📦 Dependency Checks:")
    if not check_dependencies():
        sys.exit(1)
    
    check_optional_dependencies()
    
    print("\n⚙️  Configuration Checks:")
    config_ok = check_config_file()
    
    print("\n🗄️  Database Checks:")
    db_ok = check_mongodb_connection()
    
    # Create directory structure
    print("\n📁 Directory Setup:")
    create_directory_structure()
    
    # Start server
    print("\n🚀 Starting Server:")
    if not config_ok:
        print("⚠️  Starting without full configuration. Some features may not work.")
    
    if not db_ok:
        print("⚠️  Starting without database connection. Database features will be unavailable.")
    
    print("\n" + "=" * 50)
    print("🌐 Server will start at: http://localhost:8000")
    print("📚 API docs available at: http://localhost:8000/docs")
    print("💡 Press Ctrl+C to stop the server")
    print("=" * 50)
    
    try:
        # Import and start the FastAPI app
        import uvicorn
        uvicorn.run(
            "app:app", 
            host="0.0.0.0", 
            port=8000, 
            reload=True,
            log_level="info"
        )
    except KeyboardInterrupt:
        print("\n\n👋 Server stopped by user")
    except Exception as e:
        print(f"\n❌ Error starting server: {e}")
        sys.exit(1)

if __name__ == "__main__":
    main()
