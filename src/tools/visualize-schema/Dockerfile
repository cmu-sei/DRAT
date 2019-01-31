FROM python:3.6

# Add proxy server and uncomment if needed
#
# ARG http_proxy=http://your_proxy_server_here
# ARG https_proxy=http://your_proxy_server_here

RUN pip install eralchemy
COPY requirements.txt /tmp/requirements.txt
RUN pip install -r /tmp/requirements.txt -v
RUN apt update
RUN apt -y install graphviz
COPY vis /


