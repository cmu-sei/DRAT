FROM centos:7
EXPOSE 5000
WORKDIR /app
ARG FLASK_APP=rpmatcher.py
ARG FLASK_DEBUG=1
ARG DOCKER=true

COPY docker/files/rpm-gpg/ /etc/pki/rpm-gpg/
COPY docker/files/proxy.sh /etc/profile.d/10proxy.sh
COPY docker/files/inputrc /etc/inputrc
COPY docker/files/bashrc /root/.bashrc
COPY docker/files/yum.conf /etc/yum.conf
COPY docker/files/yum.repos.d/* /etc/yum.repos.d/

RUN yum install -y deltarpm && \
    yum update -y && \
    yum install -y yum-utils which patch bsdtar python-pip

COPY ./src/rpmatcher/requirements.txt /app/requirements.txt

RUN source /etc/profile.d/10proxy.sh ; \
    pip install -U pip && \
    pip install --no-cache-dir -r /app/requirements.txt && \
    rm -vf /app/requirements.txt

COPY ./src/db /app/db
COPY ./src/rpmatcher /app

CMD ["python", "rpmatcher.py"]
