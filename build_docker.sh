#!/bin/bash
docker build \
  --build-arg AVAFRAME_VERSION=0.0.4 \
  -t avaframe:0.0.4 \
  -t avaframe:latest \
  .
