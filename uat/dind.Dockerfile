FROM docker:29.7.2-dind@sha256:12e683a161823b2a839aeea999b9d960e6e1f9a97b1679ad6b441982e2d9cf07

RUN apk add --no-cache \
    bash=5.3.9-r1 \
    curl=8.21.0-r0 \
    python3=3.14.7-r1
