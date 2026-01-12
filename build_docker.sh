#!/bin/bash
docker build \
  --build-arg AVAFRAME_VERSION=0.0.5 \
  -t avaframe:0.0.5 \
  -t avaframe:latest \
  .
