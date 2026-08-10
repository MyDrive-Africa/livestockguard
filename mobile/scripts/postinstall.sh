#!/bin/bash
# postinstall.sh — Fix @react-native dependency hoisting for Metro bundler
# When npm hoists @react-native/* packages to the top-level node_modules,
# Metro can't resolve them from react-native's Libraries/ directory.
# This copies all hoisted @react-native/* deps back into react-native/node_modules/.
set -e

MOBILE_DIR="$(cd "$(dirname "$0")/.." && pwd)"
RN_DIR="$MOBILE_DIR/node_modules/react-native"
RN_NODE_MODULES="$RN_DIR/node_modules"
RN_PKG="$RN_DIR/package.json"

if [ ! -f "$RN_PKG" ]; then
  echo "postinstall: react-native not installed yet, skipping"
  exit 0
fi

# Dynamically find all @react-native/* dependencies from react-native's package.json
PACKAGES=$(node -e "
  const pkg = require('$RN_PKG');
  const deps = Object.keys(pkg.dependencies || {}).filter(d => d.startsWith('@react-native/'));
  deps.forEach(d => console.log(d));
")

FIXED=0
for PKG in $PACKAGES; do
  HOISTED="$MOBILE_DIR/node_modules/$PKG"
  NESTED="$RN_NODE_MODULES/$PKG"

  if [ -d "$HOISTED" ] && [ ! -e "$NESTED" ]; then
    mkdir -p "$(dirname "$NESTED")"
    cp -R "$HOISTED" "$NESTED"
    echo "postinstall: copied $PKG → react-native/node_modules/"
    FIXED=$((FIXED + 1))
  fi
done

if [ $FIXED -gt 0 ]; then
  echo "postinstall: fixed $FIXED hoisted @react-native packages"
else
  echo "postinstall: all @react-native packages resolved correctly"
fi
