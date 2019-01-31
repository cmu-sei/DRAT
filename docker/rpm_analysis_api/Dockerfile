FROM centos:7
EXPOSE 5001
WORKDIR /app
COPY docker/files/pycharm-debug.egg /app/pycharm-debug.egg
COPY docker/files/rpm-gpg/ /etc/pki/rpm-gpg/
COPY docker/files/proxy.sh /etc/profile.d/10proxy.sh
COPY docker/files/inputrc /etc/inputrc
COPY docker/files/bashrc /root/.bashrc
COPY docker/files/yum.conf /etc/yum.conf
COPY docker/files/yum.repos.d/* /etc/yum.repos.d/
RUN mkdir -p /data/yum
RUN yum install -y deltarpm && \
    yum update -y && \
    yum install -y yum-utils which patch bsdtar python-pip
ADD ./src/rpmatcher/requirements.txt /app/requirements.txt
RUN source /etc/profile.d/10proxy.sh ; \
    pip install -U pip && \
    pip install --no-cache-dir -r /app/requirements.txt && \
    rm -vf /app/requirements.txt
COPY ./src/db /app/db
COPY ./src/rpmatcher /app
ENTRYPOINT flask run -p $FLASK_PORT -h $FLASK_HOST
CMD ["-c"]
