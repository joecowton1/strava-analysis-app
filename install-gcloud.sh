#!/bin/bash

# Install Google Cloud SDK (gcloud CLI) on macOS
# This script provides multiple installation methods

echo "🔧 Installing Google Cloud SDK (gcloud CLI)"
echo ""

# Check if already installed
if command -v gcloud &> /dev/null; then
    echo "✅ gcloud is already installed!"
    gcloud version
    exit 0
fi

echo "Choose an installation method:"
echo ""
echo "Option 1: Homebrew (Recommended)"
echo "  Run this command in your terminal:"
echo "  brew install --cask google-cloud-sdk"
echo ""
echo "Option 2: Manual Installation"
echo "  1. Download from: https://cloud.google.com/sdk/docs/install#mac"
echo "  2. Extract and run: ./google-cloud-sdk/install.sh"
echo ""
echo "Option 3: Quick install script (runs in your terminal)"
echo ""

read -p "Would you like to try the Homebrew installation now? (y/n) " -n 1 -r
echo
if [[ $REPLY =~ ^[Yy]$ ]]
then
    echo "Installing via Homebrew..."
    brew install --cask google-cloud-sdk
    
    echo ""
    echo "Add gcloud to your PATH by adding this to your ~/.zshrc:"
    echo 'export PATH="/opt/homebrew/share/google-cloud-sdk/bin:$PATH"'
    echo ""
    echo "Then run: source ~/.zshrc"
fi
