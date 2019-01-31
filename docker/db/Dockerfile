FROM postgres:10
EXPOSE 5432
# Uncomment and update if behind a proxy server
# ARG http_proxy=http://add_proxy_server_here
# ARG https_proxy=http://add_proxy_server_here
RUN mkdir -p /etc/pgsql && mkdir -p /data && chown -R postgres:postgres /data
COPY db/*.conf /etc/pgsql/
COPY db/docker_pg_copy.sh /docker-entrypoint-initdb.d/docker_pg_copy.sh
COPY db/docker_pg_wrapper.sh /docker_pg_wrapper.sh
ENTRYPOINT ["/bin/bash", "/docker_pg_wrapper"]
