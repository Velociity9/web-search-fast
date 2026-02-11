#!/usr/bin/env bash
# Start/stop/status for web-search-fast MCP SSE server
set -euo pipefail

PIDFILE="/tmp/web-search-mcp.pid"
LOGFILE="/tmp/web-search-mcp.log"
PYTHON="/Users/firshme/miniconda/bin/python"
HOST="127.0.0.1"
PORT="8897"
MCP_NAME="web-search-fast"
SSE_URL="http://${HOST}:${PORT}/sse"

register_mcp() {
    # Remove existing, then re-add to user scope
    claude mcp remove "$MCP_NAME" -s user 2>/dev/null || true
    claude mcp add -s user -t sse "$MCP_NAME" "$SSE_URL" 2>/dev/null
    echo "Claude MCP registered: $MCP_NAME -> $SSE_URL (scope: user)"
}

start() {
    if [ -f "$PIDFILE" ] && kill -0 "$(cat "$PIDFILE")" 2>/dev/null; then
        echo "Already running (PID $(cat "$PIDFILE"))"
        return 0
    fi
    echo "Starting $MCP_NAME MCP server on $HOST:$PORT ..."
    nohup "$PYTHON" -m src.mcp_server --transport sse --host "$HOST" --port "$PORT" \
        > "$LOGFILE" 2>&1 &
    echo $! > "$PIDFILE"
    # Wait for server to be ready
    for i in $(seq 1 30); do
        # SSE is a streaming endpoint; grab first bytes to confirm it responds
        RESP=$(curl -sf "$SSE_URL" -m 3 2>/dev/null || true)
        if echo "$RESP" | grep -q "endpoint"; then
            echo "Ready (PID $(cat "$PIDFILE")) — $SSE_URL"
            register_mcp
            return 0
        fi
        sleep 1
    done
    echo "Warning: server started but health check timed out. Check $LOGFILE"
}

stop() {
    if [ ! -f "$PIDFILE" ]; then
        echo "Not running"
        return 0
    fi
    PID=$(cat "$PIDFILE")
    if kill -0 "$PID" 2>/dev/null; then
        echo "Stopping PID $PID ..."
        kill "$PID"
        sleep 2
        kill -0 "$PID" 2>/dev/null && kill -9 "$PID" 2>/dev/null
        echo "Stopped"
    else
        echo "Stale PID file, cleaning up"
    fi
    rm -f "$PIDFILE"
}

status() {
    if [ -f "$PIDFILE" ] && kill -0 "$(cat "$PIDFILE")" 2>/dev/null; then
        echo "Running (PID $(cat "$PIDFILE"))"
        curl -sf "$SSE_URL" -m 2 2>/dev/null | head -2 && echo "SSE endpoint OK" || echo "SSE endpoint not responding"
    else
        echo "Not running"
    fi
}

restart() {
    stop
    start
}

case "${1:-start}" in
    start)   start   ;;
    stop)    stop    ;;
    status)  status  ;;
    restart) restart ;;
    *)       echo "Usage: $0 {start|stop|status|restart}" ;;
esac
