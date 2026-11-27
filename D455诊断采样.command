#!/bin/zsh
cd "$(dirname "$0")" || exit 1
print 'Diagnostic test: keep the camera fixed and both small stereo lenses clear.'
print 'First hold your RIGHT palm about 50-60 cm away for 15 seconds.'
print 'Then slowly curl and straighten the fingers for 15 seconds.'
print 'Finally move slowly nearer/farther. Q saves and exits.'
print 'Original RGB/depth/landmark samples are saved every 30 processed frames.'
exec /bin/zsh "$PWD/开始D455手部追踪.command" --depth-samples-every 30 "$@"
