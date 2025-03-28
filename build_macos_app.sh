#!/bin/bash
# Build and test the macOS app bundle

# Exit on error
set -e

echo "Building Universal Media Converter macOS app..."

# Create directories if they don't exist
mkdir -p static/img

# Check if app icon exists
if [ ! -f static/img/app_icon.icns ]; then
    echo "Warning: App icon not found at static/img/app_icon.icns"
    echo "Using a placeholder icon instead"
    
    # Create a placeholder icon if needed
    if [ ! -f static/img/app_icon.png ]; then
        echo "Creating placeholder app icon..."
        # Use macOS's system icons if available
        if [ -f /System/Library/CoreServices/CoreTypes.bundle/Contents/Resources/GenericApplicationIcon.icns ]; then
            cp /System/Library/CoreServices/CoreTypes.bundle/Contents/Resources/GenericApplicationIcon.icns static/img/app_icon.icns
        else
            echo "Error: Could not create a placeholder icon. Please create one manually."
            exit 1
        fi
    fi
fi

# Check if py2app is installed
if ! pip show py2app > /dev/null; then
    echo "Installing py2app..."
    pip install py2app
fi

# Clean previous builds
echo "Cleaning previous builds..."
rm -rf build dist

# Build the app
echo "Building macOS app bundle..."
python setup.py py2app

if [ $? -eq 0 ]; then
    echo "Build successful!"
    echo "App created at: $(pwd)/dist/Universal Media Converter.app"
    
    # Ask if user wants to run the app
    read -p "Do you want to run the app now? (y/n) " -n 1 -r
    echo
    if [[ $REPLY =~ ^[Yy]$ ]]; then
        open "dist/Universal Media Converter.app"
    fi
    
    # Ask if user wants to push to GitHub
    read -p "Do you want to push to GitHub macos branch? (y/n) " -n 1 -r
    echo
    if [[ $REPLY =~ ^[Yy]$ ]]; then
        # Check if git is initialized
        if [ ! -d .git ]; then
            echo "Git repository not initialized. Initializing..."
            git init
        fi
        
        # Check if macos branch exists
        if ! git show-ref --verify --quiet refs/heads/macos; then
            echo "Creating macos branch..."
            git checkout -b macos
        else
            echo "Switching to macos branch..."
            git checkout macos
        fi
        
        # Add files to git
        echo "Adding files to git..."
        git add .
        
        # Commit changes
        echo "Committing changes..."
        git commit -m "macOS app bundle with Docker support"
        
        # Push to GitHub
        echo "Pushing to GitHub..."
        git push -u origin macos
        
        echo "Successfully pushed to GitHub macos branch!"
    fi
else
    echo "Build failed."
    exit 1
fi

echo "Done." 