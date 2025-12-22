#!/bin/bash
docker build \
  --build-arg AVAFRAME_VERSION=0.0.1 \
  -t avaframe:0.0.1 \
  -t avaframe:latest \
  .
