#!/bin/bash
docker run --rm -p 8888:8888 -v $(pwd)/:/ap-siu-habitat/ dymaxionlabs/siu
