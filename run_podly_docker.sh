#!/bin/bash

# Colors for output
YELLOW='\033[1;33m'
RED='\033[0;31m'
GREEN='\033[0;32m'
NC='\033[0m' # No Color

# Read server URL from config.yml if it exists
SERVER_URL=""

if [ -f "config/config.yml" ]; then
    SERVER_URL=$(grep "^server:" config/config.yml | cut -d' ' -f2- | tr -d ' ')

    if [ -n "$SERVER_URL" ]; then
        # Remove http:// or https:// prefix to get just the hostname
        CLEAN_URL=$(echo "$SERVER_URL" | sed 's|^https\?://||')
        export VITE_API_URL="http://${CLEAN_URL}:5001"
        echo -e "${GREEN}Using server URL from config.yml: ${VITE_API_URL}${NC}"
    fi
fi

# Check dependencies
echo -e "${YELLOW}Checking dependencies...${NC}"
if ! command -v docker &> /dev/null; then
    echo -e "${RED}Docker not found. Please install Docker first.${NC}"
    exit 1
fi

if ! docker compose version &> /dev/null; then
    echo -e "${RED}Docker Compose not found. Please install Docker Compose V2.${NC}"
    exit 1
fi

# Default values
BUILD_ONLY=false
TEST_BUILD=false
DETACHED=false
PRODUCTION_MODE=true
REBUILD=false
BRANCH_SUFFIX="main"

# Parse command line arguments
while [[ $# -gt 0 ]]; do
    case "$1" in
        --build)
            BUILD_ONLY=true
            ;;
        --test-build)
            TEST_BUILD=true
            ;;
        -d|--detach|-b|--background)
            DETACHED=true
            ;;
        --dev)
            REBUILD=true
            PRODUCTION_MODE=false
            ;;
        --rebuild)
            REBUILD=true
            ;;
        --production)
            PRODUCTION_MODE=true
            ;;
        --branch=*)
            BRANCH_NAME="${1#*=}"
            BRANCH_SUFFIX="${BRANCH_NAME}"
            ;;
        -h|--help)
            echo "Usage: $0 [OPTIONS]"
            echo ""
            echo "Options:"
            echo "  --build             Build containers only (don't start)"
            echo "  --test-build        Test build with no cache"
            echo "  -d, --detach        Run in detached/background mode"
            echo "  -b, --background    Alias for --detach"
            echo "  --dev               Development mode (rebuild containers)"
            echo "  --rebuild           Rebuild containers before starting"
            echo "  --production        Use published images (default)"
            echo "  --branch=BRANCH     Use specific branch images"
            echo "  -h, --help          Show this help message"
            exit 0
            ;;
        *)
            echo "Unknown argument: $1"
            echo "Usage: $0 [--build] [--test-build] [-d|--detach] [-b|--background] [--dev] [--rebuild] [--production] [--branch=BRANCH_NAME] [-h|--help]"
            exit 1
            ;;
    esac
    shift
done

# Get current user's UID and GID
export PUID=$(id -u)
export PGID=$(id -g)

# Surface authentication/session configuration warnings
REQUIRE_AUTH_LOWER=$(printf '%s' "${REQUIRE_AUTH:-false}" | tr '[:upper:]' '[:lower:]')
if [ "$REQUIRE_AUTH_LOWER" = "true" ]; then
    if [ -z "${PODLY_SECRET_KEY}" ]; then
        echo -e "${YELLOW}Warning: REQUIRE_AUTH is true but PODLY_SECRET_KEY is not set. Sessions will be reset on every restart.${NC}"
    fi
fi

# Setup Docker Compose configuration
if [ "$PRODUCTION_MODE" = true ]; then
    COMPOSE_FILES="-f compose.yml"
    BRANCH="${BRANCH_SUFFIX}-latest"
    export BRANCH

    echo -e "${YELLOW}Production mode - using published images${NC}"
    echo -e "${YELLOW}  Branch tag: ${BRANCH}${NC}"
    if [ "$BRANCH_SUFFIX" != "main" ]; then
        echo -e "${GREEN}Using custom branch: ${BRANCH_SUFFIX}${NC}"
    fi
else
    export DEVELOPER_MODE=true
    COMPOSE_FILES="-f compose.yml"
    if [ "$REBUILD" = true ]; then
        echo -e "${YELLOW}Rebuild mode - will rebuild containers before starting${NC}"
    fi
fi

# Execute appropriate Docker Compose command
if [ "$BUILD_ONLY" = true ]; then
    echo -e "${YELLOW}Building containers only...${NC}"
    if ! docker compose $COMPOSE_FILES build; then
        echo -e "${RED}Build failed! Please fix the errors above and try again.${NC}"
        exit 1
    fi
    echo -e "${GREEN}Build completed successfully.${NC}"
elif [ "$TEST_BUILD" = true ]; then
    echo -e "${YELLOW}Testing build with no cache...${NC}"
    if ! docker compose $COMPOSE_FILES build --no-cache; then
        echo -e "${RED}Build failed! Please fix the errors above and try again.${NC}"
        exit 1
    fi
    echo -e "${GREEN}Test build completed successfully.${NC}"
else
    # Handle development rebuild
    if [ "$REBUILD" = true ]; then
        echo -e "${YELLOW}Rebuilding containers...${NC}"
        if ! docker compose $COMPOSE_FILES build; then
            echo -e "${RED}Build failed! Please fix the errors above and try again.${NC}"
            exit 1
        fi
    fi

    if [ "$DETACHED" = true ]; then
        echo -e "${YELLOW}Starting Podly in detached mode...${NC}"
        docker compose $COMPOSE_FILES up -d
        echo -e "${GREEN}Podly is running in the background.${NC}"
        echo -e "${GREEN}Application: http://localhost:5001${NC}"
    else
        echo -e "${YELLOW}Starting Podly...${NC}"
        echo -e "${GREEN}Application will be available at: http://localhost:5001${NC}"
        docker compose $COMPOSE_FILES up
    fi
fi
