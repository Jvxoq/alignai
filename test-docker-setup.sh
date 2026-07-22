#!/bin/bash

# AlignAI Docker Setup Test Script
# This script verifies that all services are running correctly

set -e

echo "🔍 AlignAI Docker Setup Test"
echo "=============================="
echo ""

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

# Test counter
TOTAL_TESTS=0
PASSED_TESTS=0

# Function to run a test
run_test() {
    local test_name="$1"
    local test_command="$2"

    TOTAL_TESTS=$((TOTAL_TESTS + 1))
    echo -n "Testing: $test_name... "

    if eval "$test_command" > /dev/null 2>&1; then
        echo -e "${GREEN}✓ PASS${NC}"
        PASSED_TESTS=$((PASSED_TESTS + 1))
        return 0
    else
        echo -e "${RED}✗ FAIL${NC}"
        return 1
    fi
}

# Function to test HTTP endpoint
test_http() {
    local url="$1"
    curl -f -s -o /dev/null "$url"
}

# Check if Docker is running
echo "Checking Docker availability..."
if ! docker info > /dev/null 2>&1; then
    echo -e "${RED}✗ Docker is not running. Please start Docker Desktop.${NC}"
    exit 1
fi
echo -e "${GREEN}✓ Docker is running${NC}"
echo ""

# Check if services are running
echo "Checking if services are running..."
if ! docker-compose ps | grep -q "alignai"; then
    echo -e "${YELLOW}⚠ Services are not running. Starting them now...${NC}"
    echo "This may take a few minutes on first run..."
    docker-compose up -d
    echo "Waiting 30 seconds for services to initialize..."
    sleep 30
fi
echo ""

# Run tests
echo "Running health checks..."
echo "----------------------"

# Test 1: Postgres
run_test "PostgreSQL" "docker-compose exec -T postgres pg_isready -U postgres"

# Qdrant runs on Qdrant Cloud (not in Compose) — nothing to health-check locally.

# Test 3: Backend Health
run_test "Backend Health" "test_http http://localhost:8000/health"

# Test 4: Backend API Docs
run_test "Backend API Docs" "test_http http://localhost:8000/docs"

# Test 5: Agent Health
run_test "Agent Health" "test_http http://localhost:8123/ok"

# NOTE: the frontend is not part of this Docker stack — it deploys to Vercel.

echo ""
echo "Testing API functionality..."
echo "---------------------------"

# Test 7: Backend API Response
echo -n "Testing: Backend Health Response... "
HEALTH_RESPONSE=$(curl -s http://localhost:8000/health)
if echo "$HEALTH_RESPONSE" | grep -q "ok"; then
    echo -e "${GREEN}✓ PASS${NC}"
    PASSED_TESTS=$((PASSED_TESTS + 1))
else
    echo -e "${RED}✗ FAIL${NC}"
fi
TOTAL_TESTS=$((TOTAL_TESTS + 1))

# Test 8: Signup endpoint (should accept request)
echo -n "Testing: Signup endpoint availability... "
SIGNUP_RESPONSE=$(curl -s -X POST http://localhost:8000/auth/signup \
    -H "Content-Type: application/json" \
    -d '{"email":"test@example.com","password":"TestPassword123!"}' \
    -w "%{http_code}" -o /dev/null)
if [ "$SIGNUP_RESPONSE" == "201" ] || [ "$SIGNUP_RESPONSE" == "409" ]; then
    echo -e "${GREEN}✓ PASS${NC}"
    PASSED_TESTS=$((PASSED_TESTS + 1))
else
    echo -e "${RED}✗ FAIL (Status: $SIGNUP_RESPONSE)${NC}"
fi
TOTAL_TESTS=$((TOTAL_TESTS + 1))

# Test 9: Rate limiting (should block after limit)
echo -n "Testing: Rate limiting... "
RATE_LIMIT_OK=true
for i in {1..6}; do
    STATUS=$(curl -s -X POST http://localhost:8000/auth/login \
        -H "Content-Type: application/json" \
        -d '{"email":"test@example.com","password":"wrong"}' \
        -w "%{http_code}" -o /dev/null)
    if [ $i -eq 6 ] && [ "$STATUS" == "429" ]; then
        echo -e "${GREEN}✓ PASS (Rate limit working)${NC}"
        PASSED_TESTS=$((PASSED_TESTS + 1))
        RATE_LIMIT_OK=true
        break
    elif [ $i -eq 6 ]; then
        echo -e "${RED}✗ FAIL (Expected 429, got $STATUS)${NC}"
        RATE_LIMIT_OK=false
        break
    fi
    sleep 0.2
done
TOTAL_TESTS=$((TOTAL_TESTS + 1))

echo ""
echo "Checking container status..."
echo "---------------------------"
docker-compose ps

echo ""
echo "=============================="
echo "Test Results: $PASSED_TESTS/$TOTAL_TESTS passed"
echo "=============================="
echo ""

if [ $PASSED_TESTS -eq $TOTAL_TESTS ]; then
    echo -e "${GREEN}🎉 All tests passed! Your Docker setup is working correctly.${NC}"
    echo ""
    echo "Access your services:"
    echo "  • Backend API Docs: http://localhost:8000/docs"
    echo "  • Frontend (Vercel, or local: cd frontend && npm run dev → http://localhost:5173)"
    echo ""
    echo "Next steps:"
    echo "  1. Start the frontend: cd frontend && npm run dev"
    echo "  2. Try the compliance audit feature"
    echo "  3. Check the logs: docker-compose logs -f"
    exit 0
else
    echo -e "${RED}❌ Some tests failed. Check the logs for details:${NC}"
    echo "  docker-compose logs -f"
    echo ""
    echo "Common fixes:"
    echo "  • Wait longer: Services may still be starting up"
    echo "  • Check ports: Make sure ports 8000, 8123, 5432, etc. are available"
    echo "  • Restart: docker-compose restart"
    exit 1
fi
