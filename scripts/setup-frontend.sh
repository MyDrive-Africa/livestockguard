#!/usr/bin/env bash
#
# LivestockGuard — Frontend & Mobile Setup (Fresh Machine)
#
# Installs and configures everything needed for:
#   - Web Dashboard (React 18 + Vite + MapLibre GL)
#   - Mobile App — Web mode (React Native + Expo, browser)
#   - Mobile App — iOS native (requires Xcode + CocoaPods)
#   - Mobile App — Android native (requires Android Studio + JDK 17)
#
# Usage:
#   bash scripts/setup-frontend.sh          # Full setup (dashboard + mobile web + native checks)
#   bash scripts/setup-frontend.sh --web    # Only dashboard + mobile web (skip native)
#   bash scripts/setup-frontend.sh --ios    # Include iOS native setup
#   bash scripts/setup-frontend.sh --android  # Include Android native setup
#
# Prerequisites (install these first):
#   - Node.js 20+ (mobile requires 20, dashboard works with 18+)
#   - npm 9+
#   - Git
#   - For iOS: Xcode 15+, CocoaPods
#   - For Android: Android Studio, JDK 17, Android SDK 34

set -e

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
ROOT_DIR="$(dirname "$SCRIPT_DIR")"
cd "$ROOT_DIR"

# ─── Parse Arguments ──────────────────────────────────────────────────────────

SETUP_IOS=false
SETUP_ANDROID=false
WEB_ONLY=false

for arg in "$@"; do
  case "$arg" in
    --web) WEB_ONLY=true ;;
    --ios) SETUP_IOS=true ;;
    --android) SETUP_ANDROID=true ;;
    --help|-h)
      echo "Usage: bash scripts/setup-frontend.sh [--web] [--ios] [--android]"
      echo "  --web       Only dashboard + mobile web (skip native checks)"
      echo "  --ios       Include iOS native setup (Xcode + CocoaPods)"
      echo "  --android   Include Android native setup (Android Studio + JDK)"
      echo "  (no flags)  Full setup with native prerequisite checks"
      exit 0
      ;;
  esac
done

# If no flags, default to full (check native prereqs but don't fail)
if [ "$WEB_ONLY" = false ] && [ "$SETUP_IOS" = false ] && [ "$SETUP_ANDROID" = false ]; then
  SETUP_IOS=true
  SETUP_ANDROID=true
fi

# ─── Colours & Logging ────────────────────────────────────────────────────────

GREEN='\033[32m'
YELLOW='\033[33m'
CYAN='\033[36m'
RED='\033[31m'
BOLD='\033[1m'
DIM='\033[2m'
RESET='\033[0m'

LOG_FILE="$ROOT_DIR/logs/setup-frontend.log"
mkdir -p "$ROOT_DIR/logs"
: > "$LOG_FILE"

log() {
  local level="$1"
  shift
  local timestamp
  timestamp="$(date '+%Y-%m-%d %H:%M:%S')"
  echo "[$timestamp] [$level] $*" >> "$LOG_FILE"
  case "$level" in
    INFO)  echo -e "  ${GREEN}✅${RESET} $*" ;;
    WARN)  echo -e "  ${YELLOW}⚠️  $*${RESET}" ;;
    ERROR) echo -e "  ${RED}❌ $*${RESET}" ;;
    STEP)  echo -e "\n${CYAN}$*${RESET}" ;;
    DETAIL) echo -e "  ${DIM}$*${RESET}" ;;
  esac
}

run_logged() {
  # Run a command, logging output to file, showing errors on failure
  echo "  [CMD] $*" >> "$LOG_FILE"
  if ! "$@" >> "$LOG_FILE" 2>&1; then
    log ERROR "Command failed: $*"
    echo "  See $LOG_FILE for details"
    return 1
  fi
}

# ─── Header ──────────────────────────────────────────────────────────────────

echo -e "${BOLD}${CYAN}"
echo "╔═══════════════════════════════════════════════════════════╗"
echo "║  LivestockGuard — Frontend & Mobile Setup                 ║"
echo "║  Fresh machine installation script                        ║"
echo "╚═══════════════════════════════════════════════════════════╝"
echo -e "${RESET}"
echo -e "${DIM}Log: $LOG_FILE${RESET}"
echo ""

# ─── Step 1: Check Core Prerequisites ────────────────────────────────────────

log STEP "[1/7] Checking core prerequisites..."

MISSING=()

# Node.js
if command -v node &> /dev/null; then
  NODE_VER=$(node -v | sed 's/v//')
  NODE_MAJOR=$(echo "$NODE_VER" | cut -d. -f1)
  if [ "$NODE_MAJOR" -ge 20 ]; then
    log INFO "Node.js $NODE_VER (>= 20 required for mobile)"
  elif [ "$NODE_MAJOR" -ge 18 ]; then
    log WARN "Node.js $NODE_VER — dashboard OK, but mobile requires Node 20+."
    log DETAIL "Upgrade: brew install node@20 (or use nvm/fnm)"
  else
    log ERROR "Node.js $NODE_VER is too old. Need 18+ (20+ for mobile)."
    MISSING+=("node>=20")
  fi
else
  log ERROR "Node.js not found"
  MISSING+=("node")
fi

# npm
if command -v npm &> /dev/null; then
  NPM_VER=$(npm -v)
  log INFO "npm $NPM_VER"
else
  log ERROR "npm not found"
  MISSING+=("npm")
fi

# Git
if command -v git &> /dev/null; then
  log INFO "git $(git --version | awk '{print $3}')"
else
  log ERROR "git not found"
  MISSING+=("git")
fi

if [ ${#MISSING[@]} -ne 0 ]; then
  echo ""
  log ERROR "Missing core prerequisites: ${MISSING[*]}"
  echo ""
  echo "  Install on macOS:"
  echo "    brew install node@20 git"
  echo ""
  echo "  Or use nvm:"
  echo "    curl -o- https://raw.githubusercontent.com/nvm-sh/nvm/v0.39.7/install.sh | bash"
  echo "    nvm install 20"
  echo ""
  exit 1
fi

# ─── Step 2: Dashboard Setup ─────────────────────────────────────────────────

log STEP "[2/7] Setting up Web Dashboard (React 18 + Vite + TailwindCSS)..."

cd "$ROOT_DIR/dashboard"

log DETAIL "Directory: dashboard/"
log DETAIL "Running: npm install"

run_logged npm install

# Verify key packages
if [ -d "node_modules/vite" ] && [ -d "node_modules/react" ]; then
  VITE_VER=$(node -e "console.log(require('./node_modules/vite/package.json').version)" 2>/dev/null || echo "?")
  REACT_VER=$(node -e "console.log(require('./node_modules/react/package.json').version)" 2>/dev/null || echo "?")
  log INFO "Dashboard dependencies installed"
  log DETAIL "Vite $VITE_VER, React $REACT_VER, MapLibre GL, TanStack Query, Zustand, TailwindCSS"
else
  log ERROR "Dashboard npm install may have failed — check $LOG_FILE"
fi

# Type check
log DETAIL "Running TypeScript type check: npx tsc --noEmit"
if npx tsc --noEmit >> "$LOG_FILE" 2>&1; then
  log INFO "TypeScript check passed (no type errors)"
else
  log WARN "TypeScript has type errors — dashboard will still run in dev mode"
fi

cd "$ROOT_DIR"

# ─── Step 3: Mobile App — Web Mode ───────────────────────────────────────────

log STEP "[3/7] Setting up Mobile App (React Native + Expo 52)..."

cd "$ROOT_DIR/mobile"

log DETAIL "Directory: mobile/"
log DETAIL "Required Node version: 20 (see mobile/.node-version)"
log DETAIL "Running: npm install"

run_logged npm install

# Verify Expo
if [ -d "node_modules/expo" ]; then
  EXPO_VER=$(node -e "console.log(require('./node_modules/expo/package.json').version)" 2>/dev/null || echo "?")
  RN_VER=$(node -e "console.log(require('./node_modules/react-native/package.json').version)" 2>/dev/null || echo "?")
  log INFO "Mobile dependencies installed"
  log DETAIL "Expo $EXPO_VER, React Native $RN_VER, react-native-maps, AsyncStorage"
else
  log ERROR "Mobile npm install may have failed — check $LOG_FILE"
fi

# Verify postinstall ran (the @react-native hoisting fix)
log DETAIL "Verifying @react-native package resolution..."
RESOLUTION_OK=$(node -e '
  const pkg = require("./node_modules/react-native/package.json");
  const deps = Object.keys(pkg.dependencies || {}).filter(d => d.startsWith("@react-native/"));
  const fs = require("fs");
  const path = require("path");
  const missing = deps.filter(d => {
    const nested = path.join("node_modules/react-native/node_modules", d);
    const hoisted = path.join("node_modules", d);
    return !fs.existsSync(nested) && !fs.existsSync(hoisted);
  });
  console.log(missing.length === 0 ? "ok" : missing.join(","));
' 2>/dev/null || echo "error")

if [ "$RESOLUTION_OK" = "ok" ]; then
  log INFO "@react-native packages resolved correctly (postinstall OK)"
else
  log WARN "Some @react-native packages missing: $RESOLUTION_OK"
  log DETAIL "Re-running postinstall fix..."
  bash scripts/postinstall.sh >> "$LOG_FILE" 2>&1 || true
fi

cd "$ROOT_DIR"

# ─── Step 4: iOS Native Prerequisites ────────────────────────────────────────

if [ "$WEB_ONLY" = true ]; then
  log STEP "[4/7] Skipping iOS native setup (--web mode)"
elif [ "$SETUP_IOS" = true ]; then
  log STEP "[4/7] Checking iOS native prerequisites..."

  IOS_READY=true

  # Xcode
  if command -v xcodebuild &> /dev/null; then
    XCODE_VER=$(xcodebuild -version 2>/dev/null | head -1 || echo "unknown")
    log INFO "$XCODE_VER"
  else
    log WARN "Xcode not installed — needed for iOS native builds"
    log DETAIL "Install: xcode-select --install (CLI tools) or App Store (full Xcode)"
    IOS_READY=false
  fi

  # CocoaPods
  if command -v pod &> /dev/null; then
    POD_VER=$(pod --version 2>/dev/null || echo "?")
    log INFO "CocoaPods $POD_VER"
  else
    log WARN "CocoaPods not installed — needed for iOS native builds"
    log DETAIL "Install: sudo gem install cocoapods (or brew install cocoapods)"
    IOS_READY=false
  fi

  # Install pods if CocoaPods is available
  if [ "$IOS_READY" = true ] && [ -f "$ROOT_DIR/mobile/ios/Podfile" ]; then
    log DETAIL "Installing CocoaPods dependencies (mobile/ios/)..."
    cd "$ROOT_DIR/mobile/ios"
    if run_logged pod install; then
      log INFO "iOS CocoaPods installed"
    else
      log WARN "pod install failed — you may need to run it manually"
      log DETAIL "cd mobile/ios && pod install"
    fi
    cd "$ROOT_DIR"
  elif [ "$IOS_READY" = true ]; then
    log DETAIL "No Podfile yet — will be generated on first 'expo run:ios'"
  fi

  if [ "$IOS_READY" = true ]; then
    log INFO "iOS native: ready"
  else
    log WARN "iOS native: not ready (web mode will still work)"
  fi
else
  log STEP "[4/7] Skipping iOS native setup (not requested)"
fi

# ─── Step 5: Android Native Prerequisites ────────────────────────────────────

if [ "$WEB_ONLY" = true ]; then
  log STEP "[5/7] Skipping Android native setup (--web mode)"
elif [ "$SETUP_ANDROID" = true ]; then
  log STEP "[5/7] Checking Android native prerequisites..."

  ANDROID_READY=true
  ANDROID_HOME="${ANDROID_HOME:-$HOME/Library/Android/sdk}"

  # Android SDK
  if [ -d "$ANDROID_HOME" ]; then
    log INFO "Android SDK found: $ANDROID_HOME"
  else
    log WARN "Android SDK not found at $ANDROID_HOME"
    log DETAIL "Install Android Studio: https://developer.android.com/studio"
    log DETAIL "Or set ANDROID_HOME to your SDK path"
    ANDROID_READY=false
  fi

  # JDK 17
  if command -v java &> /dev/null; then
    JAVA_VER=$(java -version 2>&1 | head -1)
    log INFO "Java: $JAVA_VER"
    # Check if it's JDK 17
    if echo "$JAVA_VER" | grep -q "17"; then
      log DETAIL "JDK 17 detected (required for React Native 0.76+)"
    else
      log WARN "JDK 17 recommended for React Native 0.76. Current: $JAVA_VER"
      log DETAIL "Install: brew install openjdk@17"
    fi
  else
    log WARN "Java/JDK not found — needed for Android builds"
    log DETAIL "Install: brew install openjdk@17"
    ANDROID_READY=false
  fi

  # adb
  if command -v adb &> /dev/null || [ -f "$ANDROID_HOME/platform-tools/adb" ]; then
    log INFO "adb available"
  else
    log WARN "adb not found — install Android SDK Platform-Tools"
    ANDROID_READY=false
  fi

  # Setup local.properties
  if [ "$ANDROID_READY" = true ]; then
    mkdir -p "$ROOT_DIR/mobile/android"
    echo "sdk.dir=$ANDROID_HOME" > "$ROOT_DIR/mobile/android/local.properties"
    log INFO "Created mobile/android/local.properties"
  fi

  # Check for emulator AVDs
  if [ "$ANDROID_READY" = true ]; then
    if command -v emulator &> /dev/null || [ -f "$ANDROID_HOME/emulator/emulator" ]; then
      AVDS=$("$ANDROID_HOME/emulator/emulator" -list-avds 2>/dev/null | head -3 || echo "")
      if [ -n "$AVDS" ]; then
        log INFO "Android emulators available: $(echo "$AVDS" | tr '\n' ', ')"
      else
        log WARN "No AVDs found. Create one in Android Studio > Virtual Device Manager"
      fi
    fi
  fi

  if [ "$ANDROID_READY" = true ]; then
    log INFO "Android native: ready"
  else
    log WARN "Android native: not ready (web mode will still work)"
  fi
else
  log STEP "[5/7] Skipping Android native setup (not requested)"
fi

# ─── Step 6: Environment Configuration ───────────────────────────────────────

log STEP "[6/7] Configuring environment..."

# Dashboard .env (API URL)
if [ ! -f "$ROOT_DIR/dashboard/.env" ]; then
  cat > "$ROOT_DIR/dashboard/.env" << 'EOF'
# LivestockGuard Dashboard — Environment
VITE_API_URL=http://localhost:8000
VITE_WS_URL=ws://localhost:8000/ws
VITE_MAPLIBRE_STYLE=https://basemaps.cartocdn.com/gl/positron-gl-style/style.json
EOF
  log INFO "Created dashboard/.env (API URL, WebSocket, MapLibre style)"
else
  log INFO "dashboard/.env already exists"
fi

# Mobile .env (API URL)
if [ ! -f "$ROOT_DIR/mobile/.env" ]; then
  cat > "$ROOT_DIR/mobile/.env" << 'EOF'
# LivestockGuard Mobile — Environment
API_URL=http://localhost:8000
WS_URL=ws://localhost:8000/ws
EOF
  log INFO "Created mobile/.env (API URL)"
else
  log INFO "mobile/.env already exists"
fi

cd "$ROOT_DIR"

# ─── Step 7: Verification & Summary ──────────────────────────────────────────

log STEP "[7/7] Verifying setup..."

DASH_OK=false
MOBILE_OK=false

# Dashboard sanity check
if [ -d "$ROOT_DIR/dashboard/node_modules/vite" ]; then
  DASH_OK=true
  log INFO "Dashboard: ready (npm run dev → http://localhost:5173)"
fi

# Mobile sanity check
if [ -d "$ROOT_DIR/mobile/node_modules/expo" ]; then
  MOBILE_OK=true
  log INFO "Mobile web: ready (npx expo start --web → http://localhost:8082)"
fi

echo ""
echo -e "${BOLD}${GREEN}╔═══════════════════════════════════════════════════════════╗${RESET}"
echo -e "${BOLD}${GREEN}║  Frontend Setup Complete!                                  ║${RESET}"
echo -e "${BOLD}${GREEN}╠═══════════════════════════════════════════════════════════╣${RESET}"
echo -e "${GREEN}║                                                           ║${RESET}"
if [ "$DASH_OK" = true ]; then
echo -e "${GREEN}║  ✅ Dashboard         make dashboard    → :5173           ║${RESET}"
else
echo -e "${YELLOW}║  ⚠️  Dashboard         (check logs)                        ║${RESET}"
fi
if [ "$MOBILE_OK" = true ]; then
echo -e "${GREEN}║  ✅ Mobile (web)      make mobile-web   → :8082           ║${RESET}"
else
echo -e "${YELLOW}║  ⚠️  Mobile (web)      (check logs)                        ║${RESET}"
fi
if [ "$SETUP_IOS" = true ] && [ "${IOS_READY:-false}" = true ]; then
echo -e "${GREEN}║  ✅ Mobile (iOS)      make mobile-ios                     ║${RESET}"
elif [ "$SETUP_IOS" = true ]; then
echo -e "${YELLOW}║  ⚠️  Mobile (iOS)      missing prerequisites              ║${RESET}"
fi
if [ "$SETUP_ANDROID" = true ] && [ "${ANDROID_READY:-false}" = true ]; then
echo -e "${GREEN}║  ✅ Mobile (Android)  make mobile-android                 ║${RESET}"
elif [ "$SETUP_ANDROID" = true ]; then
echo -e "${YELLOW}║  ⚠️  Mobile (Android)  missing prerequisites              ║${RESET}"
fi
echo -e "${GREEN}║                                                           ║${RESET}"
echo -e "${GREEN}║  Quick start:                                             ║${RESET}"
echo -e "${GREEN}║    make dashboard       # Web dashboard                   ║${RESET}"
echo -e "${GREEN}║    make mobile-web      # Mobile in browser               ║${RESET}"
echo -e "${GREEN}║    make run-all         # Everything with logging         ║${RESET}"
echo -e "${GREEN}║                                                           ║${RESET}"
echo -e "${GREEN}║  Full log: $LOG_FILE  ║${RESET}"
echo -e "${BOLD}${GREEN}╚═══════════════════════════════════════════════════════════╝${RESET}"
echo ""
