#DRAT Database and RPM Matcher service

DRAT uses a Postgres database to store the scrape and analysis results. The database runs in a Docker container.

DRAT also uses a web service to get original package files and provide a UI to match RPM files to installed RPMs. This runs in two Docker containers (API and back-end).

These containers are wired-up on a Docker network, specified in the `docker-compose.yml` file here. Start all of them with:

```shell
$ docker-compose up
```

This will stream the container consoles to you terminal window. Add "-d" at the end to run the containers in the background. End later with 

```shell
$ docker-compose down
```
