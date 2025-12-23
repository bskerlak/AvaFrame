#!/bin/bash
docker build \
  --build-arg AVAFRAME_VERSION=0.0.3 \
  -t avaframe:0.0.3 \
  -t avaframe:latest \
  .
