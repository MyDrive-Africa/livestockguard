// metro.config.js — LivestockGuard Mobile
const { getDefaultConfig } = require('expo/metro-config');
const path = require('path');

const config = getDefaultConfig(__dirname);

// Fix hoisted dependency resolution — ensures Metro can always find
// @react-native/* packages that npm hoists out of react-native/node_modules
const rnPkg = require('./node_modules/react-native/package.json');
const rnDeps = Object.keys(rnPkg.dependencies || {}).filter(d => d.startsWith('@react-native/'));
const extraModules = { ...config.resolver.extraNodeModules };
rnDeps.forEach(dep => {
  const depPath = path.resolve(__dirname, 'node_modules', dep);
  try {
    require('fs').statSync(depPath);
    extraModules[dep] = depPath;
  } catch (e) { /* not installed, skip */ }
});
config.resolver.extraNodeModules = extraModules;

// Ensure Metro watches the top-level node_modules
config.watchFolders = [
  ...(config.watchFolders || []),
  path.resolve(__dirname, 'node_modules'),
];

// Shim native-only modules for web platform
const originalResolveRequest = config.resolver.resolveRequest;

config.resolver.resolveRequest = (context, moduleName, platform) => {
  // react-native-maps doesn't support web — use our placeholder shim
  if (platform === 'web' && moduleName === 'react-native-maps') {
    return {
      filePath: path.resolve(__dirname, 'src/shims/react-native-maps.web.tsx'),
      type: 'sourceFile',
    };
  }

  if (originalResolveRequest) {
    return originalResolveRequest(context, moduleName, platform);
  }
  return context.resolveRequest(context, moduleName, platform);
};

module.exports = config;
