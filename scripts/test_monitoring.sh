#!/bin/bash
#
# UptimeRobot Monitoring Test Script
# Tests the health check endpoints to verify they work correctly
#

set -e  # Exit on error

# Colors for output
GREEN='\033[0;32m'
RED='\033[0;31m'
BLUE='\033[0;34m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

# Configuration
BASE_URL="${1:-http://localhost:5000}"
CF_ACCESS_CLIENT_ID="${CF_ACCESS_CLIENT_ID:-}"
CF_ACCESS_CLIENT_SECRET="${CF_ACCESS_CLIENT_SECRET:-}"

AUTH_HEADERS=()
if [ -n "$CF_ACCESS_CLIENT_ID" ] || [ -n "$CF_ACCESS_CLIENT_SECRET" ]; then
    if [ -z "$CF_ACCESS_CLIENT_ID" ] || [ -z "$CF_ACCESS_CLIENT_SECRET" ]; then
        echo -e "${RED}✗ FAILED${NC} - CF_ACCESS_CLIENT_ID and CF_ACCESS_CLIENT_SECRET must be provided together"
        exit 1
    fi
    AUTH_HEADERS=(-H "CF-Access-Client-Id: ${CF_ACCESS_CLIENT_ID}" -H "CF-Access-Client-Secret: ${CF_ACCESS_CLIENT_SECRET}")
fi

echo -e "${BLUE}========================================${NC}"
echo -e "${BLUE}   UptimeRobot Monitoring Test${NC}"
echo -e "${BLUE}========================================${NC}"
echo ""
echo -e "Testing endpoint: ${YELLOW}${BASE_URL}${NC}"
echo ""

# Test 1: Basic health check
echo -e "${BLUE}Test 1: Basic Health Check (/health)${NC}"
echo "Testing: ${BASE_URL}/health"
RESPONSE=$(curl -s -w "\n%{http_code}" "${AUTH_HEADERS[@]}" "${BASE_URL}/health")
HTTP_CODE=$(echo "$RESPONSE" | tail -n1)
BODY=$(echo "$RESPONSE" | head -n-1)

if [ "$HTTP_CODE" = "200" ] && [ "$BODY" = "ok" ]; then
    echo -e "${GREEN}✓ PASSED${NC} - Health check returned 200 OK"
    echo "  Response: $BODY"
else
    echo -e "${RED}✗ FAILED${NC} - Expected 200 'ok', got $HTTP_CODE '$BODY'"
    exit 1
fi
echo ""

# Test 2: bounded status signals
echo -e "${BLUE}Test 2: Status Signals (/health/status)${NC}"
echo "Testing: ${BASE_URL}/health/status"
RESPONSE=$(curl -s -w "\n%{http_code}" "${AUTH_HEADERS[@]}" "${BASE_URL}/health/status")
HTTP_CODE=$(echo "$RESPONSE" | tail -n1)
BODY=$(echo "$RESPONSE" | head -n-1)

if [ "$HTTP_CODE" = "200" ]; then
    echo -e "${GREEN}✓ PASSED${NC} - Status signals returned 200 OK"
    echo "  Response preview:"
    echo "$BODY" | head -c 200
    echo "..."

    # Validate the response contract, not just the presence of a field name.
    if echo "$BODY" | jq -e '
        (.signals | type == "array") and
        all(.signals[]; type == "object" and (.key | type == "string"))
    ' >/dev/null; then
        echo -e "${GREEN}✓${NC} Response contains expected JSON structure"
    else
        echo -e "${RED}✗ FAILED${NC} - Response must contain a signals array with string key values"
        exit 1
    fi
else
    echo -e "${RED}✗ FAILED${NC} - Expected 200, got $HTTP_CODE"
    echo "  Response: $BODY"
    exit 1
fi
echo ""

# Test 3: Verify access policy behavior
echo -e "${BLUE}Test 3: Access Policy${NC}"
if [ -n "$CF_ACCESS_CLIENT_ID" ]; then
    echo "Verifying service-token access to the Cloudflare-gated endpoints..."
else
    echo "Verifying direct access to the endpoints..."
fi

# Test with explicit no-credentials
RESPONSE=$(curl -s -w "\n%{http_code}" -H "Cookie: " "${AUTH_HEADERS[@]}" "${BASE_URL}/health")
HTTP_CODE=$(echo "$RESPONSE" | tail -n1)

if [ "$HTTP_CODE" = "200" ]; then
    echo -e "${GREEN}✓ PASSED${NC} - /health accepted the configured access path"
else
    echo -e "${RED}✗ FAILED${NC} - /health endpoint may require authentication"
    exit 1
fi

# Test /health/status with explicit no-credentials
RESPONSE=$(curl -s -w "\n%{http_code}" -H "Cookie: " "${AUTH_HEADERS[@]}" "${BASE_URL}/health/status")
HTTP_CODE=$(echo "$RESPONSE" | tail -n1)

if [ "$HTTP_CODE" = "200" ]; then
    echo -e "${GREEN}✓ PASSED${NC} - /health/status accepted the configured access path"
else
    echo -e "${RED}✗ FAILED${NC} - /health/status endpoint may require authentication"
    exit 1
fi
echo ""

# Summary and UptimeRobot Configuration
echo -e "${BLUE}========================================${NC}"
echo -e "${GREEN}All tests passed!${NC}"
echo -e "${BLUE}========================================${NC}"
echo ""
echo -e "${YELLOW}UptimeRobot Configuration Guide:${NC}"
echo ""
echo "1. Basic Monitoring (Recommended):"
echo "   URL: ${BASE_URL}/health"
echo "   Expected Response: 'ok'"
echo "   Expected Status: 200"
echo ""
echo "2. Advanced Monitoring (Optional):"
echo "   URL: ${BASE_URL}/health/status"
echo "   Expected Response: Contains bounded 'signals'"
echo "   Expected Status: 200"
echo ""
echo -e "${YELLOW}Next Steps:${NC}"
echo "1. Add monitor in UptimeRobot dashboard"
echo "2. Set monitoring interval (5 minutes recommended)"
echo "3. Create public status page"
echo "4. Set STATUS_PAGE_URL environment variable"
echo "   Example: export STATUS_PAGE_URL='https://stats.uptimerobot.com/your-page'"
echo ""
echo -e "${BLUE}========================================${NC}"
