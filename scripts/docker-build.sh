#!/bin/bash

# Discord Stream Bot - Docker Build Script for Linux/macOS
# This script provides Docker build and management functionality

set -e  # Exit on any error

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

print_info() {
    echo -e "${BLUE}[INFO]${NC} $1"
}

print_success() {
    echo -e "${GREEN}[SUCCESS]${NC} $1"
}

print_warning() {
    echo -e "${YELLOW}[WARNING]${NC} $1"
}

print_error() {
    echo -e "${RED}[ERROR]${NC} $1"
}

print_header() {
    echo -e "\n${BLUE}=== $1 ===${NC}"
}

show_help() {
    echo "Discord Stream Bot - Docker Build Script"
    echo ""
    echo "Usage: $0 [COMMAND]"
    echo ""
    echo "Commands:"
    echo "  build         Build Docker image"
    echo "  run           Build and run with Docker Compose"
    echo "  stop          Stop Docker containers"
    echo "  logs          Show Docker logs"
    echo "  clean         Clean up Docker resources"
    echo "  rebuild       Clean and rebuild everything"
    echo "  help          Show this help"
    echo ""
    echo "Examples:"
    echo "  $0 build         # Build Docker image"
    echo "  $0 run           # Build and run with compose"
    echo "  $0 clean         # Clean up resources"
    echo ""
}

build_image() {
    print_header "Building Docker Image"

    # Change to project root (script is in scripts/ subdirectory)
    cd "$(dirname "$0")/.."

    print_info "Building discord-stream-bot image..."
    docker build -t discord-stream-bot .

    print_success "Docker image built successfully"
}

run_compose() {
    print_header "Running with Docker Compose"

    # Change to project root
    cd "$(dirname "$0")/.."

    if [[ ! -f "config.ini" ]]; then
        print_error "config.ini not found. Please create it from config/config.ini.dist"
        print_info "Run: cp config/config.ini.dist config.ini"
        exit 1
    fi

    print_info "Starting services with Docker Compose..."
    docker-compose up -d --build

    print_success "Services started successfully"
    print_info "Use '$0 logs' to view logs"
    print_info "Use '$0 stop' to stop services"
}

stop_containers() {
    print_header "Stopping Docker Containers"

    cd "$(dirname "$0")/.."

    print_info "Stopping Docker Compose services..."
    docker-compose down

    print_success "Containers stopped"
}

show_logs() {
    print_header "Docker Logs"

    cd "$(dirname "$0")/.."

    print_info "Showing Docker Compose logs (Ctrl+C to exit)..."
    docker-compose logs -f
}

clean_resources() {
    print_header "Cleaning Docker Resources"

    cd "$(dirname "$0")/.."

    print_info "Stopping and removing containers..."
    docker-compose down --volumes --remove-orphans

    print_info "Removing Discord Stream Bot images..."
    docker rmi discord-stream-bot 2>/dev/null || true
    docker rmi ghcr.io/yourusername/discordstreambot 2>/dev/null || true

    print_info "Pruning unused Docker resources..."
    docker system prune -f

    print_success "Docker resources cleaned"
}

rebuild_all() {
    print_header "Rebuilding Everything"

    clean_resources
    build_image

    print_success "Rebuild complete"
    print_info "Use 'docker-compose up -d' to start services"
}

main() {
    case "${1:-help}" in
        "build")
            build_image
            ;;
        "run")
            run_compose
            ;;
        "stop")
            stop_containers
            ;;
        "logs")
            show_logs
            ;;
        "clean")
            clean_resources
            ;;
        "rebuild")
            rebuild_all
            ;;
        "help"|"-h"|"--help")
            show_help
            ;;
        *)
            print_error "Unknown command: $1"
            echo ""
            show_help
            exit 1
            ;;
    esac
}

main "$@"
