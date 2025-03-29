#!/bin/bash
# NZB4 Universal Media Converter - Dashboard Launcher
# Opens the web dashboard in the default browser

# Set colors for output
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

echo -e "${BLUE}NZB4 Universal Media Converter - Dashboard${NC}"

# Check if dashboard directory exists
if [ -d "dashboard" ]; then
    echo -e "${GREEN}Opening dashboard in browser...${NC}"
    
    # Get absolute path to the dashboard
    DASHBOARD_PATH="$(pwd)/dashboard/index.html"
    
    # Try different methods based on OS
    if command -v xdg-open &> /dev/null; then
        # Linux
        xdg-open "file://${DASHBOARD_PATH}"
    elif command -v open &> /dev/null; then
        # macOS
        open "file://${DASHBOARD_PATH}"
    elif command -v start &> /dev/null; then
        # Windows
        start "file://${DASHBOARD_PATH}"
    else
        echo -e "${YELLOW}Could not open browser automatically.${NC}"
        echo -e "Please open this URL in your browser:"
        echo -e "${GREEN}file://${DASHBOARD_PATH}${NC}"
    fi
    
    # Check if services are running
    if docker ps | grep -q "nzb4-flask-api\|nzb4-express-api"; then
        echo -e "${GREEN}NZB4 services are running.${NC}"
    else
        echo -e "${YELLOW}Warning: NZB4 services don't appear to be running.${NC}"
        echo -e "You can start them with: ${GREEN}./run.sh start${NC}"
    fi
else
    echo -e "${RED}Error: Dashboard not found.${NC}"
    echo -e "Please ensure the 'dashboard' directory exists with index.html inside."
    echo -e "If you haven't set up NZB4 yet, please run: ${GREEN}./setup.sh${NC}"
    exit 1
fi 