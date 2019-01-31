FROM alpine:3.8
# Proxy settings go here or --build-arg
# ARG http_proxy=http://your_proxy_server
# ARG https_proxy=http://your_proxy_server
RUN addgroup -S testssh && \
    adduser -s /bin/ash -S -G testssh testssh && \
    echo "testssh:testssh" | chpasswd
RUN apk --no-cache add \
    openssh

RUN mkdir -p /home/testssh/.ssh
COPY testssh/testssh_id_rsa.pub /home/testssh/.ssh/authorized_keys
COPY testssh/test_file.txt /home/testssh/test_file.txt
COPY testssh/entry.sh /entry.sh
RUN chmod 700 /home/testssh/.ssh && \
    chmod 600 /home/testssh/.ssh/authorized_keys && \
    chown -R testssh:testssh /home/testssh/.ssh && \
    echo "PasswordAuthentication no" >> /etc/ssh/sshd_config

EXPOSE 22
ENTRYPOINT ["/entry.sh"]
