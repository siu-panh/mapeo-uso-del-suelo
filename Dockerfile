# Ubuntu as base image
FROM ubuntu:latest

RUN mkdir ap-siu-habitat

# Copiando requirements  al container
COPY ./requirements.txt /ap-siu-habitat/requirements.txt 

RUN apt-get update
RUN apt-get install -y software-properties-common
RUN apt-get -y install wget

# Instalando python3 
RUN apt-get -y install python3
RUN apt-get -y install python3-dev
RUN apt-get -y install python3-pip


# Instalando GDAL 
RUN add-apt-repository ppa:ubuntugis/ppa
RUN apt-get update
RUN apt-get -y install libgdal-dev gdal-bin libspatialindex-dev libsm6 libxext6 libxrender-dev

# Instalando extension de GDAL para Python y otras extensiones necesarias 
RUN export CPLUS_INCLUDE_PATH=/usr/include/gdal
RUN export C_INCLUDE_PATH=/usr/include/gdal


RUN pip3 install --upgrade pip
RUN pip3 install -r /ap-siu-habitat/requirements.txt
RUN pip3 install GDAL==$(gdal-config --version) --global-option=build_ext --global-option="-I/usr/include/gdal"

EXPOSE 8888


CMD ["/ap-siu-habitat/init_install.sh"]

# Ejecutar docker container
#docker run -p 8888:8888 -v ~/Desarrollos/ap-siu-habitat/:/ap-siu-habitat/ siu

#Ejecutar container en background e interactivo con bash 
#docker run -v ~/Desarrollos/ap-siu-habit	at/:/ap-siu-habitat/ -dit siu bash --name ap-siu-habitat


