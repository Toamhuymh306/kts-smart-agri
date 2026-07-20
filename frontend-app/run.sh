#!/bin/bash

# KTs Smart Agriculture - Frontend Server Startup Script
# Chạy: ./run.sh

echo "🌾 KTs Smart Agriculture - Frontend"
echo "=================================="
echo ""

# Check if Python is installed
if command -v python3 &> /dev/null; then
    echo "✅ Sử dụng Python HTTP Server"
    echo "🚀 Mở: http://localhost:8000"
    echo ""
    echo "Press Ctrl+C để dừng"
    echo ""
    python3 -m http.server 8000
# Check if Node.js is installed
elif command -v node &> /dev/null; then
    echo "✅ Sử dụng Node.js HTTP Server"

    # Check if http-server is installed
    if ! command -v http-server &> /dev/null; then
        echo "📦 Cài đặt http-server..."
        npm install -g http-server
    fi

    echo "🚀 Mở: http://localhost:8080"
    echo ""
    echo "Press Ctrl+C để dừng"
    echo ""
    http-server -p 8080
else
    echo "❌ Lỗi: Chưa cài Python hoặc Node.js"
    echo ""
    echo "Vui lòng cài một trong hai:"
    echo "  • Python: https://www.python.org/downloads/"
    echo "  • Node.js: https://nodejs.org/"
    exit 1
fi
