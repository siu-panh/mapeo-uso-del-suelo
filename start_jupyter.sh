#!/bin/bash
jupyter notebook --generate-config

echo
echo "** Please enter a password for your Jupyter Notebook. **"
echo
jupyter notebook password

# Iniciando jupyter notebook
#jupyter notebook --ip=0.0.0.0 --no-browser
jupyter notebook --ip=0.0.0.0 --allow-root
