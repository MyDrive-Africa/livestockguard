#!/bin/bash
# run-android.sh — Full clean build & run for LivestockGuard Android
# Usage: bash scripts/run-android.sh [--clean]
#   --clean: nuke node_modules and reinstall (use after SDK upgrades)
set -e

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
MOBILE_DIR="$(cd "$SCRIPT_DIR/.." && pwd)"

cd "$MOBILE_DIR"

echo "============================================="
echo " LivestockGuard — Android Build & Run"
echo "============================================="
echo ""

# ─── 1. Environment Setup ────────────────────────────────────────────────────
export ANDROID_HOME="${ANDROID_HOME:-$HOME/Library/Android/sdk}"
export PATH="$ANDROID_HOME/emulator:$ANDROID_HOME/platform-tools:$ANDROID_HOME/tools:$PATH"

if [ ! -d "$ANDROID_HOME" ]; then
  echo "ERROR: ANDROID_HOME not found at $ANDROID_HOME"
  echo "  Set ANDROID_HOME to your Android SDK path."
  exit 1
fi

echo "[env] ANDROID_HOME: $ANDROID_HOME"

# Check for connected device or running emulator
if ! adb devices 2>/dev/null | grep -q "device$"; then
  echo "[emu] No Android device/emulator detected. Starting emulator..."
  EMULATOR=$(emulator -list-avds 2>/dev/null | head -1)
  if [ -n "$EMULATOR" ]; then
    echo "[emu] Starting: $EMULATOR"
    emulator -avd "$EMULATOR" -no-snapshot-load &
    echo "[emu] Waiting for device to boot..."
    adb wait-for-device
    sleep 10
  else
    echo "ERROR: No AVDs found. Create one in Android Studio first."
    exit 1
  fi
fi
echo "[env] Android device connected"
echo ""

# ─── 2. Clean (optional or if --clean flag) ──────────────────────────────────
if [ "$1" = "--clean" ] || [ ! -d "node_modules" ]; then
  echo "[clean] Removing node_modules, caches, build artifacts..."
  rm -rf node_modules package-lock.json .expo
  rm -rf android/app/build android/.gradle
  rm -rf /tmp/metro-*
  echo "[clean] Done"
  echo ""
fi

# ─── 3. Install Dependencies ─────────────────────────────────────────────────
echo "[npm] Installing dependencies..."
npm install
echo "[npm] Done"
echo ""

# ─── 4. Verify @react-native resolution ──────────────────────────────────────
# The postinstall script handles this, but verify it worked
echo "[verify] Checking @react-native dependency resolution..."
MISSING=$(node -e '
  const pkg = require("./node_modules/react-native/package.json");
  const deps = Object.keys(pkg.dependencies || {}).filter(d => d.startsWith("@react-native/"));
  const fs = require("fs");
  const path = require("path");
  const missing = deps.filter(d => !fs.existsSync(path.join("node_modules/react-native/node_modules", d)));
  if (missing.length > 0) { console.log(missing.join(",")); process.exit(1); }
' 2>&1) || true

if [ -n "$MISSING" ]; then
  echo "[verify] Re-running postinstall to fix: $MISSING"
  bash scripts/postinstall.sh
fi
echo "[verify] All @react-native packages resolved"
echo ""

# ─── 5. Clear Metro cache ────────────────────────────────────────────────────
echo "[metro] Clearing bundler cache..."
rm -rf /tmp/metro-*
rm -rf node_modules/.cache
echo "[metro] Done"
echo ""

# ─── 6. Build & Run ──────────────────────────────────────────────────────────
echo "[build] Building and launching on Android..."
echo ""

npx expo run:android
