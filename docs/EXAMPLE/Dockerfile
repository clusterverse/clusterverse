FROM ubuntu:24.04
ARG DEBIAN_FRONTEND=noninteractive
ENV TZ=Europe/London
SHELL ["/bin/bash", "-c"]

RUN ln -snf /usr/share/zoneinfo/$TZ /etc/localtime && echo $TZ > /etc/timezone \
    && apt-get update && apt-get install -y git iproute2 python3 python3-pip \
    && pip3 --no-cache-dir install --break-system-packages ansible>=10.4.0 \
    && pip3 --no-cache-dir install --break-system-packages -r $(pip3 --no-cache-dir show ansible | grep ^Location | sed -r 's/^Location: (.*)/\1/')/ansible_collections/azure/azcollection/requirements*.txt \
    && apt-get install -y python3-boto3 python3-dev python3-google-auth python3-jinja2 python3-jmespath python3-libvirt python3-lxml python3-netaddr python3-paramiko python3-pycdlib python3-setuptools python3-wheel python3-xmltodict \
    && apt-get clean && rm -rf /var/lib/apt/lists/*


COPY . .

RUN ansible-galaxy install -r requirements.yml
