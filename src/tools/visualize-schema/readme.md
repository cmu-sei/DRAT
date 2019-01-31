#Create an ER diagram of the DRAT database schema

DRAT uses a Postgres database to store the scrape and analysis results. This tool creates a diagram of the schema.

First, start the database container. It is defined in iac-code/docker. cd to that directory, and 

`docker-compose up`

You may also have to re-initialize the schema; change to `src/` directory and run `alembic upgrade head`.

Then, from this directory, 

`docker-compose up`

This will (re)create the file *schema.pdf*, which will show the schema.

We use *eralchemy* to generate the visualization, and the dependencies for that are all packaged up in a Docker container. We need to use docker-compose so we can connect the container to the Docker network where the database is running. The container execution should exit with code "0".
