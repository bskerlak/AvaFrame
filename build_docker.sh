#!/bin/bash
docker build \
  --build-arg AVAFRAME_VERSION=0.0.6 \
  -t avaframe:0.0.6 \
  -t avaframe:latest \
  .
