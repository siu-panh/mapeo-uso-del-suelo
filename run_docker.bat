@echo off
docker run -ti --rm -p 8888:8888 -v "%cd%"/:/ap-siu-habitat/ dymaxionlabs/siu
