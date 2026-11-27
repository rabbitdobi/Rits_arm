#!/bin/zsh
set -eu
cd "$(dirname "$0")"
mkdir -p .build
swiftc Sources/DepthStatistics.swift Tests/main.swift -o .build/depth-core-tests
.build/depth-core-tests
