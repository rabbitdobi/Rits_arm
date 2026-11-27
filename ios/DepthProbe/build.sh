#!/bin/zsh
set -eu
cd "$(dirname "$0")"
if [[ -z "${DEVELOPER_DIR:-}" && -d /Applications/Xcode.app/Contents/Developer ]]; then
  export DEVELOPER_DIR=/Applications/Xcode.app/Contents/Developer
fi
if ! xcrun --find xcodebuild >/dev/null 2>&1; then
  print -u2 'Full Xcode is required. Install it from the App Store and launch it once to finish setup.'
  exit 1
fi
xcodebuild -project DepthProbe.xcodeproj -scheme DepthProbe -configuration Debug \
  -destination 'generic/platform=iOS' -derivedDataPath DerivedData CODE_SIGNING_ALLOWED=NO build
