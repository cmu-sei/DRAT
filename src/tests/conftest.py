#------------------------------------------------------------------------------
# DRAT Prototype Tool Source Code
# 
# Copyright 2019 Carnegie Mellon University. All Rights Reserved.
# 
# NO WARRANTY. THIS CARNEGIE MELLON UNIVERSITY AND SOFTWARE ENGINEERING 
# INSTITUTE MATERIAL IS FURNISHED ON AN "AS-IS" BASIS. CARNEGIE MELLON
# UNIVERSITY MAKES NO WARRANTIES OF ANY KIND, EITHER EXPRESSED OR IMPLIED, AS
# TO ANY MATTER INCLUDING, BUT NOT LIMITED TO, WARRANTY OF FITNESS FOR PURPOSE
# OR MERCHANTABILITY, EXCLUSIVITY, OR RESULTS OBTAINED FROM USE OF THE
# MATERIAL. CARNEGIE MELLON UNIVERSITY DOES NOT MAKE ANY WARRANTY OF ANY KIND
# WITH RESPECT TO FREEDOM FROM PATENT, TRADEMARK, OR COPYRIGHT INFRINGEMENT.
# 
# Released under a MIT (SEI)-style license, please see license.txt or contact
# permission@sei.cmu.edu for full terms.
# 
# [DISTRIBUTION STATEMENT A] This material has been approved for public
# release and unlimited distribution.  Please see Copyright notice for non-US
# Government use and distribution.
# 
# This Software includes and/or makes use of the following Third-Party
# Software subject to its own license:
# 
# 1. Python 3.7 (https://docs.python.org/3/license.html)
# Copyright 2001-2019 Python Software Foundation.
# 
# 2. SQL Alchemy (https://github.com/sqlalchemy/sqlalchemy/blob/master/LICENSE)
# Copyright 2005-2019 SQLAlchemy authors and contributor.
# 
# DM19-0055
#------------------------------------------------------------------------------

import os
import logging
import time
import sys
from pathlib import Path
import pytest
import docker.errors
from docker import from_env
from docker.models.containers import Container, ExecResult, Image
import alembic.config
import utils.session

log = logging.getLogger(__name__)

WORKING_PATH = Path(
    os.path.dirname(
        os.path.abspath(__file__)
    )
).expanduser().resolve()

client = from_env()


def stop_container(name=None):
    if not name:
        raise ValueError("name required to stop container")

    containers = client.containers.list(all=True, filters={"name": name})

    if containers:
        for container in containers:
            try:
                log.info("\nStopping container %s" % container.short_id)
                container.stop(timeout=10)
            except Exception as e:
                log.error("Exception occurred while stopping db container: %s" % e)

            try:
                container.remove(force=True)
                log.info("Removed container %s" % container.short_id)
            except Exception as e:
                pass
    else:
        log.info("Did not find containers with the name of %s." % name)


def teardown_db():

    log.info("\nTearing down db")
    stop_container("testdb")
    log.info("done")


def get_image(name=None, dockerfile=None) -> Image:
    if not name:
        raise ValueError("Image name required")

    try:
        result = client.images.get(name)
    except docker.errors.ImageNotFound:
        result = build_image(
            dockerfile=dockerfile,
            name=name
        )

    return result


def build_image(name=None, dockerfile=None) -> Image:
    if not name or not dockerfile:
        raise ValueError("method requires name and dockerfile")

    result = client.images.build(
        dockerfile=dockerfile,
        path=WORKING_PATH.as_posix(),
        rm=True,
        tag=name,
    )

    return result[0]



@pytest.fixture()
def get_test_path() -> Path:
    return WORKING_PATH


@pytest.fixture(scope="session")
def test_sshd(request=None):
    log.info("\nsetting up sshd container")
    name = "testsshd"

    stop_container(name=name)

    image = get_image(
        name="testsshd:latest",
        dockerfile="testssh/Dockerfile"
    )

    container: Container = client.containers.run(
        image=image.id,
        name=name,
        detach=True,
        ports={
            "22/tcp": "22220",
        },
    )

    time.sleep(1)

    keyfile = WORKING_PATH.joinpath("testssh/testssh_id_rsa").as_posix()

    with utils.session.State.get_ssh_session(
        hostname="localhost",
        username="testssh",
        port=22220,
        key_file=keyfile,
    ) as s:
        yield s

    stop_container(name=name)
    log.info("done with sshd")


@pytest.fixture(scope="session")
def test_database(request=None):

    log.info("\nsetting up db")
    stop_container("testdb")

    for name in (
        "DOCKER_TLS_VERIFY",
        "DOCKER_HOST",
        "DOCKER_CERT_PATH",
        "DOCKER_MACHINE_NAME",
    ):
        try:
            del os.environ[name]
        except KeyError:
            pass

    log.info("starting db")
    container: Container = client.containers.run(
        "postgres:10",
        remove=True,
        name="testdb",
        detach=True,
        environment={
            "POSTGRES_USER": "iac",
            "POSTGRES_PASSWORD": "ia-code",
            "POSTGRES_DB": "iacode",
        },
        ports={
            "5432/tcp": "5433",
        },
        volumes={
            "%s/files/" % WORKING_PATH: {
                "bind": "/data/",
            },
            "%s/sql/" % WORKING_PATH: {
                "bind": "/docker-entrypoint-initdb.d/",
            }
        },
    )

    log.info("waiting for db")
    db_check = 1
    while db_check != 0:
        result = container.exec_run("ls -l /run/postgresql/.s.PGSQL.5432")
        if result.exit_code == 0:
            db_check = 0
        elif db_check > 30:
            raise Exception("Unable to start db")
        else:
            db_check += 1
        time.sleep(1)

    log.info("restoring test db")
    result: ExecResult = container.exec_run(
        cmd=(
            "bash -c 'xz -dc /data/test_backup.sqlc.xz | "
            "pg_restore -c -d iacode -U iac --if-exists'"
        ),
        user="postgres",
    )

    if result.exit_code != 0:
        raise Exception("Unable to restore db -> %s" % result.output)

    log.info("Wrote test backup")

    log.info("Running Alembic upgrade on test instance")

    alembic.config.main(
        argv=[
            "-c",
            "%s/../alembic_test.ini" % WORKING_PATH,
            "upgrade",
            "head",
        ]
    )
    os.environ["PGPORT"] = "5433"
    os.environ["PGUSER"] = "iac"
    os.environ["PGPASSWORD"] = "ia-code"
    os.environ["PGDATABASE"] = "iacode"

    log.info("Loading system..")
    log.info("%s" % utils.session.State.get_system(name="testsystem").name)

    yield

    teardown_db()


if __name__ == "__main__":
    try:
        test_database()
    except Exception as e:
        log.error(e)
        pass

    teardown_db()
