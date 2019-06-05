#!/bin/bash

wd=`pwd`

docker run -p 8888:8888 -v $wd/:/ap-siu-habitat/ siu
