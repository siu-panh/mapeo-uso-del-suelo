#!/bin/bash

# Instalando MpGlue
cd /ap-siu-habitat/mpglue
python3 setup.py install

# Instalando spfeas
cd /ap-siu-habitat/spfeas
python3 setup.py install

# Iniciar jupyter
cd /ap-siu-habitat
./start_jupyter.sh