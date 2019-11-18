#!/bin/bash
docker run -ti --rm -p 8888:8888 -v $(pwd)/:/ap-siu-habitat/ dymaxionlabs/siu
