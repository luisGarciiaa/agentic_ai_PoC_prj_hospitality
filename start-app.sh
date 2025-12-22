#!/bin/bash

# Change to the prj-docker-compose directory where docker compose.yaml is located
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR/prj-docker-compose" || { echo "Error: Cannot change to prj-docker compose directory"; exit 1; }

# Function to check if containers are running
check_running_containers() {
  # Check for running containers from docker compose.yaml
  local running_services=$(docker compose ps --services --filter "status=running" 2>/dev/null)
  local running_containers=0
  
  if [ -n "$running_services" ]; then
    running_containers=$(echo "$running_services" | grep -v '^$' | wc -l)
  fi
  
  if [ "$running_containers" -gt 0 ]; then
    echo "WARNING: There are already $running_containers containers running from this docker compose configuration."
    echo "Running containers:"
    echo "$running_services"
    
    if [ "$FORCE" != true ]; then
      echo ""
      echo "ERROR: This could be dangerous. To continue anyway, use the --force option."
      echo "Stopping script execution for safety."
      exit 1
    else
      echo ""
      echo "WARNING: --force option detected. Proceeding despite running containers..."
      echo "This may cause unexpected behavior or data loss."
      echo ""
    fi
  fi
}

# Function to check the functional status of services
check_service_health() {
  echo ""
  echo "🔍 Checking service health..."
  local all_healthy=true
  local wait_time=3  # Time to wait before initial checks in seconds
  local max_retries=3  # Number of retries for each service
  local retry_delay=2  # Time to wait between retries in seconds

  # Wait a bit before checking API services
  echo "  Waiting ${wait_time} seconds for services to initialize..."
  sleep $wait_time

  # Helper function to check API with retries
  check_api_with_retry() {
    local service_name="$1"
    local port="$2"
    local retries=0
    
    while [ $retries -lt $max_retries ]; do
      local status=$(curl -s -o /dev/null -w "%{http_code}" http://localhost:${port}/ --connect-timeout 5 --max-time 10)
      
      if [[ "$status" == "200" ]]; then
        echo "✅ OK (Status: 200)"
        return 0
      else
        retries=$((retries + 1))
        if [ $retries -lt $max_retries ]; then
          echo "⏳ Attempt $retries failed (Status: $status), retrying in ${retry_delay}s..."
          sleep $retry_delay
        else
          echo "❌ Not responding properly after $max_retries attempts (Final Status: $status)"
          echo "     Attempting detailed diagnostics..."
          curl -v http://localhost:${port}/ 2>&1 | grep ">" || echo "     No additional information available"
          return 1
        fi
      fi
    done
  }

  # Check AI Agents API (8010)
  if [ "$NO_AI_AGENT" != true ]; then
    echo -n "  Checking AI Agents API/Frontend(8001)... "
    if ! check_api_with_retry "AI Agents API/Frontend" "8001"; then
      all_healthy=false
    fi
  fi
 

   # Check Vector DB (Chroma)
  echo -n "  Checking Vector DB (Chroma) on localhost:8002... "
  local chroma_status=$(curl -s -o /dev/null -w "%{http_code}" http://localhost:8002/api/v2/heartbeat --connect-timeout 5 --max-time 10)
  if [[ "$chroma_status" == "200" ]]; then
    echo "✅ OK (Status: 200)"
  else
    echo "❌ Not responding properly (Status: $chroma_status)"
    all_healthy=false
  fi


  # Check PostgreSQL (bookings-db)
  echo -n "  Checking PostgreSQL connection (bookings-db)... "
  if docker exec bookings-db pg_isready -U "${POSTGRES_USER:-postgres}" -d "${POSTGRES_DB:-hospitality_db}" >/dev/null 2>&1; then
    echo "✅ OK"
  else
    echo "❌ Failed to connect to PostgreSQL"
    all_healthy=false
  fi

  if [ "$all_healthy" = true ]; then
    echo "✨ All services appear to be healthy!"
    return 0
  else 
    echo "⚠️  ERROR: Some services are not responding correctly."
    echo "ℹ️  Shutting down all services..."
    echo "ℹ️  Please check the logs for troubleshooting information."
    
    # Show the location of the logs if they're being captured
    if [ "$CAPTURE_LOGS" = true ] && [ -n "$LOG_FILE" ]; then
      echo "📝 Log file: $LOG_FILE"
    fi
    
    # Return to root directory and perform cleanup
    cd "$SCRIPT_DIR" || exit 1
    ./stop-app.sh --remove-volumes
    
    return 1
  fi
}

# Function to display help
show_help() {
  echo "Usage: $0 [--logs|-l] [--buildnocache|-bn] [--build|-b] [--no_ai_agent|-na] [--force|-f] [--help|-h]"
  echo ""
  echo "Options:"
  echo "  --logs, -l         : Capture logs continuously in the background"
  echo "  --buildnocache, -bn: Execute docker compose up with --build --no-cache"
  echo "  --build, -b        : Execute docker compose up with --build (uses cache)"
  echo "  --no_ai_agent, -na : Don't start the ai_agents api service, i.e. for debug purposes"
  echo "  --force, -f        : Force execution even if containers are already running (USE WITH CAUTION)"
  echo "  --help, -h         : Show this help message"
  echo ""
  echo "Examples:"
  echo "  $0                   Start containers without log capture"
  echo "  $0 --logs            Start containers with background log capture"
  echo "  $0 --buildnocache    Rebuild containers without cache and start them"
  echo "  $0 --build           Rebuild containers with cache and start them"
  echo "  $0 --logs --build    Combine options: rebuild with cache and start with logs"
  echo "  $0 --no_ai_agent     Start only database services (without ai_agents api)"
  echo "  $0 --force           Force execution even if containers are already running"
  exit 0
}

# Process arguments
CAPTURE_LOGS=false
BUILD_FLAG=""
BUILD_NOCACHE=false
NO_AI_AGENT=false
FORCE=false

for arg in "$@"; do
  case "$arg" in
    --help|-h)
      show_help
      ;;
    --logs|-l)
      CAPTURE_LOGS=true
      ;;
    --buildnocache|-bn)
      BUILD_NOCACHE=true
      ;;
    --build|-b)
      BUILD_FLAG="--build"
      ;;
    --no_ai_agent|-na)
      NO_AI_AGENT=true
      ;;
    --force|-f)
      FORCE=true
      ;;
    *)
      echo "Error: Unknown parameter '$arg'"
      echo "Use '$0 --help' to see the complete help"
      exit 1
      ;;
  esac
done

# Check for running containers before performing any action
check_running_containers

# Only create directory for logs if necessary
if [ "$CAPTURE_LOGS" = true ]; then
  # Create directory for logs if it doesn't exist (in project root)
  LOGS_DIR="$SCRIPT_DIR/logs"
  mkdir -p "$LOGS_DIR"

  # Generate filename with timestamp in required format
  TIMESTAMP=$(date +"%Y%m%d_%H%M%S")
  LOG_FILE="$LOGS_DIR/app_complete_$TIMESTAMP.log"

  # Display relative path to user
  REL_LOG_FILE="logs/$(basename "$LOG_FILE")"
  echo "Starting docker compose. Logs will be saved in: $REL_LOG_FILE"

  # Limit old log files (keep only the 10 most recent)
  cleanup_old_logs() {
    echo "Cleaning up old logs (keeping the 10 most recent)..."
    find "$LOGS_DIR" -name "app_complete_*.log" -type f | sort -r | tail -n +11 | xargs -r rm
    find "$LOGS_DIR" -name "app_complete_*_[0-9][0-9][0-9].log" -type f | sort -r | tail -n +21 | xargs -r rm
  }

  cleanup_old_logs
fi

# Configure docker compose command according to parameters
if [ "$BUILD_NOCACHE" = true ]; then
  echo "Building containers without cache..."
  docker compose build --no-cache
  docker compose up -d
elif [ -n "$BUILD_FLAG" ]; then
  echo "Building containers with cache..."
  docker compose up -d --build
else
  echo "Starting containers..."
  docker compose up -d
fi

# Only work with logs if the parameter was specified
if [ "$CAPTURE_LOGS" = true ]; then
  # Function to rotate logs with sequential numbering
  rotate_log() {
    local base_name=$(basename "$LOG_FILE" .log)
    local timestamp=${base_name#app_complete_}
    
    # Find the highest existing number for this timestamp
    local highest_num=0
    for existing in "$LOGS_DIR"/app_complete_${timestamp}_*.log; do
      if [ -f "$existing" ]; then
        num=$(echo "$existing" | grep -o '_[0-9][0-9][0-9]\.log$' | tr -d '_.' | sed 's/log//')
        if [ -n "$num" ] && [ "$num" -gt "$highest_num" ]; then
          highest_num=$num
        fi
      fi
    done
    
    # Increment the number for the new rotated file
    local next_num=$((highest_num + 1))
    local padded_num=$(printf "%03d" $next_num)
    local new_name="$LOGS_DIR/app_complete_${timestamp}_${padded_num}.log"
    
    echo "Rotating log to: $new_name"
    mv "$LOG_FILE" "$new_name"
    
    # Create a new main log file keeping the original timestamp
    LOG_FILE="$LOGS_DIR/app_complete_${timestamp}.log"
    echo "Continuing log capture in: $LOG_FILE"
    
    return 0
  }

  # Unattended mode: start log capture in the background
  # Solution: Use docker compose logs but force it to think it's writing to a TTY
  # by using 'script' with a proper PTY. However, since that's not working reliably,
  # we'll use a different approach: run docker compose logs through a process that
  # maintains TTY characteristics. The key insight: the old logs had ANSI codes,
  # so we need to preserve that behavior.
  
  # ANSI color codes for service prefixes (matching docker compose default colors)
  # These match what docker compose uses: green for some services, yellow for others, cyan for others
  # Using $'\033' syntax to ensure escape sequences are properly interpreted
  COLOR_RESET=$'\033[0m'
  COLOR_GREEN=$'\033[32m'   # bookings-db-data-loader
  COLOR_YELLOW=$'\033[33m'  # bookings-db  
  COLOR_CYAN=$'\033[36m'    # ai_agents_hospitality-api
  
  # Save the PID in a file to be able to stop it later
  (
    # Wait a moment for containers to be fully started
    sleep 2
    
    # Use docker compose logs but pipe through a process that adds colors
    # We'll use docker compose logs and then add colored prefixes manually
    # This ensures colors are always present
    docker compose logs -f 2>/dev/null | while IFS= read -r line || [ -n "$line" ]; do
      # Add ANSI color codes based on service name (matching docker compose behavior)
      colored_line="$line"
      if [[ "$line" =~ ^(ai_agents_hospitality-api[[:space:]]+\|) ]]; then
        colored_line="${COLOR_CYAN}${line}${COLOR_RESET}"
      elif [[ "$line" =~ ^(bookings-db[[:space:]]+\|) ]]; then
        colored_line="${COLOR_YELLOW}${line}${COLOR_RESET}"
      elif [[ "$line" =~ ^(bookings-db-data-loader[[:space:]]+\|) ]]; then
        colored_line="${COLOR_GREEN}${line}${COLOR_RESET}"
      fi
      
      printf '%b\n' "$colored_line" >> "$LOG_FILE"
      
      # Check file size and rotate if necessary
      if [ $(stat -c%s "$LOG_FILE") -gt 10485760 ]; then  # 10MB in bytes
        echo "Log file has reached maximum size. Rotating logs..." >> "$LOG_FILE"
        rotate_log
        
        # Automatic cleanup after rotation
        cleanup_old_logs
      fi
    done
  ) &
  
  # Save PID for later management
  PID=$!
  echo $PID > "$LOGS_DIR/app_complete-logger.pid"
fi

# Don't start the ai_agents api service if the parameter was specified
if [ "$NO_AI_AGENT" = true ]; then
  echo "The ai_agents api service will not be started."
  docker compose stop ai_agents_hospitality-api

fi

# Display application URLs and service information
echo ""
echo "=================================================================="
echo "                    APPLICATION INFORMATION                       "
echo "=================================================================="

# Check if ai_agents api is running
if [ "$NO_AI_AGENT" != true ]; then
  echo "🌐 AI Agents API:"
  echo "   URL: http://localhost:8001"
fi

echo ""
echo "🗄️  PostgreSQL Database:"
echo "   Host: localhost"
echo "   Port: ${POSTGRES_PORT:-5432}"
echo "   Database: ${POSTGRES_DB:-hospitality_db}"
echo "   User: ${POSTGRES_USER:-postgres}"

echo ""
echo ""
echo "🧠 Vector DB (Chroma):"
echo "   URL (debug): http://localhost:8002"
echo ""

echo "📊 Container Status:"
docker compose ps

# Check service health
check_service_health

echo ""
echo "📋 Useful Commands:"
if [ "$CAPTURE_LOGS" = true ]; then
  # Convert absolute paths to relative paths for display
  REL_LOG_FILE="logs/$(basename "$LOG_FILE")"
  REL_LOGS_DIR="logs"
  echo "   📝 Log Capture Active - File: $REL_LOG_FILE"
  echo "   View captured logs: tail -f $REL_LOG_FILE"
  echo "   Stop log capture: kill \$(cat $REL_LOGS_DIR/app_complete-logger.pid)"
  echo "   ────────────────────────────────────────"
fi
echo "   Stop all services: ./stop-app.sh"
if [ "$CAPTURE_LOGS" != true ]; then
  echo "   Start with log capture: $0 --logs"
fi

echo ""
echo "=================================================================="

