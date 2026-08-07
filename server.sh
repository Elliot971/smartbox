#!/usr/bin/env bash
set -e

COMPOSE="docker compose -f docker-compose.prod.yml --env-file .env.production"
COMPOSE_DEV="docker compose -f docker-compose.yml"

usage() {
    echo "Usage: $0 {start|stop|restart|logs|status|build} {production|dev}"
    echo "Examples:"
    echo "  $0 start production"
    echo "  $0 restart production"
    echo "  $0 logs production backend"
    echo "  $0 status production"
    exit 1
}

if [ $# -lt 2 ]; then
    usage
fi

ACTION=$1
ENV=$2
SERVICE=${3:-}

case "$ENV" in
    production|prod)
        ENV_FILE=".env.production"
        ;;
    development|dev)
        ENV_FILE=".env"
        ;;
    *)
        usage
        ;;
esac

if [ ! -f "$ENV_FILE" ] && [ "$ENV" = "production" ]; then
    if [ ! -f ".env.production.example" ]; then
        echo "Error: .env.production.example not found"
        exit 1
    fi
    echo "Creating $ENV_FILE from .env.production.example..."
    cp .env.production.example "$ENV_FILE"
    echo "Please edit $ENV_FILE before running again."
    exit 1
fi

case "$ENV" in
    production|prod)
        case "$ACTION" in
            start)
                echo "Starting production services..."
                $COMPOSE up -d --build
                ;;
            stop)
                echo "Stopping production services..."
                $COMPOSE down
                ;;
            restart)
                echo "Restarting production services..."
                $COMPOSE down
                $COMPOSE up -d --build
                ;;
            logs)
                echo "Showing production logs..."
                if [ -n "$SERVICE" ]; then
                    $COMPOSE logs -f "$SERVICE"
                else
                    $COMPOSE logs -f
                fi
                ;;
            status)
                $COMPOSE ps
                ;;
            build)
                echo "Building production images..."
                $COMPOSE build --no-cache
                ;;
            *)
                usage
                ;;
        esac
        ;;
    development|dev)
        case "$ACTION" in
            start)
                echo "Starting dev MySQL container..."
                $COMPOSE_DEV up -d mysql
                echo "MySQL is running. Start backend/frontend manually:"
                echo "  cd backend && .venv/bin/python run.py"
                echo "  cd frontend && npm run dev"
                ;;
            stop)
                echo "Stopping dev MySQL container..."
                $COMPOSE_DEV down
                ;;
            restart)
                echo "Restarting dev MySQL container..."
                $COMPOSE_DEV down
                $COMPOSE_DEV up -d mysql
                ;;
            logs)
                if [ -n "$SERVICE" ]; then
                    $COMPOSE_DEV logs -f "$SERVICE"
                else
                    $COMPOSE_DEV logs -f
                fi
                ;;
            status)
                $COMPOSE_DEV ps
                ;;
            *)
                usage
                ;;
        esac
        ;;
esac
