#!/bin/bash

# Fix gcloud CLI installation and Python configuration
# This script adds gcloud to PATH and configures Python

echo "🔧 Fixing gcloud CLI installation"
echo ""

GCLOUD_SDK="/opt/homebrew/share/google-cloud-sdk"

if [ ! -d "$GCLOUD_SDK" ]; then
    echo "❌ gcloud SDK not found at $GCLOUD_SDK"
    echo "Please install with: brew install --cask google-cloud-sdk"
    exit 1
fi

echo "✅ gcloud SDK found at: $GCLOUD_SDK"
echo ""

# Check which Python to use (prefer system Python over venv)
PYTHON_PATH="/opt/homebrew/bin/python3.13"
if [ ! -f "$PYTHON_PATH" ]; then
    PYTHON_PATH="/opt/homebrew/bin/python3.14"
fi

echo "Using Python: $PYTHON_PATH"
echo ""

# Create configuration commands for shell
echo "📝 Add these lines to your ~/.zshrc file:"
echo ""
echo "# Google Cloud SDK"
echo "export PATH=\"$GCLOUD_SDK/bin:\$PATH\""
echo "export CLOUDSDK_PYTHON=\"$PYTHON_PATH\""
echo ""

# Ask if user wants to auto-append
read -p "Would you like to automatically add these to ~/.zshrc? (y/n) " -n 1 -r
echo
if [[ $REPLY =~ ^[Yy]$ ]]; then
    # Backup .zshrc
    cp ~/.zshrc ~/.zshrc.backup
    echo "✅ Backed up ~/.zshrc to ~/.zshrc.backup"
    
    # Add to .zshrc if not already present
    if ! grep -q "google-cloud-sdk" ~/.zshrc; then
        echo "" >> ~/.zshrc
        echo "# Google Cloud SDK" >> ~/.zshrc
        echo "export PATH=\"$GCLOUD_SDK/bin:\$PATH\"" >> ~/.zshrc
        echo "export CLOUDSDK_PYTHON=\"$PYTHON_PATH\"" >> ~/.zshrc
        echo "✅ Added gcloud configuration to ~/.zshrc"
    else
        echo "⚠️  gcloud already configured in ~/.zshrc"
    fi
    
    echo ""
    echo "🎉 Done! Now run:"
    echo "  source ~/.zshrc"
    echo "  gcloud version"
else
    echo ""
    echo "Please manually add the lines above to your ~/.zshrc"
fi
