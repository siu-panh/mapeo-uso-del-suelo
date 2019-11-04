# Ubuntu as base image
FROM ubuntu:18.04

RUN apt-get update \
	&& apt-get install -y software-properties-common

RUN add-apt-repository ppa:ubuntugis/ppa \
	&& apt-get update \
	&& apt-get install --no-install-recommends -y \
		software-properties-common \
		python3 \
		python3-dev \
		python3-pip \
		wget \
		libgdal-dev \
		gdal-bin \ 
		libspatialindex-dev \
		libsm6 \
		libxext6 \
		libxrender-dev \
	&& rm -rf /var/lib/apt/lists/*

RUN mkdir /ap-siu-habitat

RUN pip3 install --upgrade pip

RUN apt-get update && apt-get install -y python3-setuptools build-essential

# Install pip dependencies
COPY ./requirements.txt /ap-siu-habitat/requirements.txt 
RUN pip3 install -r /ap-siu-habitat/requirements.txt

# Install GDAL for Python
ENV CPLUS_INCLUDE_PATH /usr/include/gdal
ENV C_INCLUDE_PATH /usr/include/gdal
RUN pip3 install GDAL==$(gdal-config --version) \
		--global-option=build_ext \
		--global-option="-I/usr/include/gdal"

EXPOSE 8888

CMD ["/ap-siu-habitat/init_install.sh"]