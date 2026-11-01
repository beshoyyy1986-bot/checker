#!/bin/bash
# ═══════════════════════════════════════════════════════════
# Gate Hunter Integration Test Script
# ═══════════════════════════════════════════════════════════

echo "╔══════════════════════════════════════════════════════════╗"
echo "║     🧪 Gate Hunter Integration Test                     ║"
echo "║     Testing Module Imports & Functionality              ║"
echo "╚══════════════════════════════════════════════════════════╝"
echo ""

# Color codes
GREEN='\033[0;32m'
RED='\033[0;31m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

# Counter
TESTS_PASSED=0
TESTS_FAILED=0

# Function: test result
print_test() {
    if [ $1 -eq 0 ]; then
        echo -e "${GREEN}✅ PASS${NC}: $2"
        TESTS_PASSED=$((TESTS_PASSED+1))
    else
        echo -e "${RED}❌ FAIL${NC}: $2"
        TESTS_FAILED=$((TESTS_FAILED+1))
    fi
}

echo "📦 Testing Module Imports..."
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"

# Test 1: Basic import
python -c "from modules.gate_hunter import deep_scan_url, search_dork" 2>/dev/null
print_test $? "Import main functions"

# Test 2: Signatures
python -c "from modules.gate_hunter.signatures import PAYMENT_GATEWAYS, SECURITY_SIGNATURES; print(f'  - {len(PAYMENT_GATEWAYS)} gateways, {len(SECURITY_SIGNATURES)} security systems')" 2>/dev/null
print_test $? "Load signatures"

# Test 3: Config
python -c "from modules.gate_hunter.config import load_config, save_config" 2>/dev/null
print_test $? "Config management"

# Test 4: Database
python -c "from modules.gate_hunter.database import init_db, db_stats; init_db(); print('  - Database initialized')" 2>/dev/null
print_test $? "Database operations"

# Test 5: Bright Data
python -c "from modules.gate_hunter.bright_data import search_dork, SEARCH_ENGINES; print(f'  - {len(SEARCH_ENGINES)} search engines')" 2>/dev/null
print_test $? "Bright Data integration"

# Test 6: Scanner
python -c "from modules.gate_hunter.scanner import deep_scan_url, _detect_security, _detect_gateways" 2>/dev/null
print_test $? "Scanner functions"

# Test 7: Handlers
python -c "from modules.gate_hunter.handlers import main_kb, search_kb, settings_kb" 2>/dev/null
print_test $? "Telegram handlers"

echo ""
echo "📊 Testing File Structure..."
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"

# Test 8: Check files exist
[ -f "modules/gate_hunter/__init__.py" ] && \
[ -f "modules/gate_hunter/signatures.py" ] && \
[ -f "modules/gate_hunter/config.py" ] && \
[ -f "modules/gate_hunter/database.py" ] && \
[ -f "modules/gate_hunter/bright_data.py" ] && \
[ -f "modules/gate_hunter/scanner.py" ] && \
[ -f "modules/gate_hunter/handlers.py" ]
print_test $? "All module files exist"

# Test 9: Check directories
[ -d "config" ] && [ -d "data" ] && [ -d "modules" ]
print_test $? "Required directories exist"

# Test 10: Check bot.py updated
grep -q "gatehunter_main" bot.py
print_test $? "bot.py contains Gate Hunter integration"

# Test 11: Check requirements.txt
grep -q "beautifulsoup4" requirements.txt
print_test $? "requirements.txt updated"

echo ""
echo "🔍 Testing Code Quality..."
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"

# Test 12: No syntax errors
python -m py_compile modules/gate_hunter/signatures.py 2>/dev/null
print_test $? "signatures.py - no syntax errors"

python -m py_compile modules/gate_hunter/config.py 2>/dev/null
print_test $? "config.py - no syntax errors"

python -m py_compile modules/gate_hunter/database.py 2>/dev/null
print_test $? "database.py - no syntax errors"

python -m py_compile modules/gate_hunter/bright_data.py 2>/dev/null
print_test $? "bright_data.py - no syntax errors"

python -m py_compile modules/gate_hunter/scanner.py 2>/dev/null
print_test $? "scanner.py - no syntax errors"

python -m py_compile modules/gate_hunter/handlers.py 2>/dev/null
print_test $? "handlers.py - no syntax errors"

echo ""
echo "📚 Testing Documentation..."
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"

# Test 13: Documentation files
[ -f "QUICK_START.md" ] && \
[ -f "INTEGRATION_GUIDE.md" ] && \
[ -f "GATE_HUNTER_SUMMARY.txt" ] && \
[ -f "modules/gate_hunter/README.md" ]
print_test $? "All documentation files exist"

echo ""
echo "╔══════════════════════════════════════════════════════════╗"
echo "║                    Test Summary                          ║"
echo "╚══════════════════════════════════════════════════════════╝"
echo ""
echo -e "${GREEN}✅ Passed: $TESTS_PASSED${NC}"
echo -e "${RED}❌ Failed: $TESTS_FAILED${NC}"
echo ""

if [ $TESTS_FAILED -eq 0 ]; then
    echo -e "${GREEN}╔══════════════════════════════════════════════════════════╗${NC}"
    echo -e "${GREEN}║     🎉 All Tests Passed! Integration Successful!        ║${NC}"
    echo -e "${GREEN}╚══════════════════════════════════════════════════════════╝${NC}"
    echo ""
    echo "🚀 Next Steps:"
    echo "   1. Run: python bot.py"
    echo "   2. Open Telegram and test Gate Hunter"
    echo "   3. Check logs for any errors"
    echo ""
    exit 0
else
    echo -e "${RED}╔══════════════════════════════════════════════════════════╗${NC}"
    echo -e "${RED}║     ⚠️  Some Tests Failed - Review Needed                ║${NC}"
    echo -e "${RED}╚══════════════════════════════════════════════════════════╝${NC}"
    echo ""
    exit 1
fi
