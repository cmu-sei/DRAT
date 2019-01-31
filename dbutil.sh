#!/bin/bash -e
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


base_path=$(dirname $(realpath $0))

app=""
arg=""
volumes=""

build_volumes() {

    vol=""

    if [[ -z ${DOCKER_MACHINE_NAME} ]]; then
        if [ -e src/db ] && [ -d src/db ]; then
            vol="-v ${base_path}/src/db:/src/db"
        fi

        if [ -e src/alembic_docker.ini ]; then
            vol+=" -v ${base_path}/src/alembic_docker.ini:/src/alembic.ini"
        fi

        if [ -e src/migration ] && [ -d src/migration ]; then
            vol+=" -v ${base_path}/src/migration:/src/migration"
        fi

        printf "%s" "${vol}"
    fi

}

cd ${base_path}

while [[ -n $1 ]]; do
    case $1 in
        "build")
            docker-compose \
                -f ${base_path}/docker/docker-compose.yml \
                -f ${base_path}/docker/docker-compose.db.yml \
                build dbutils
            exit $?
        ;;
        "backup")
            app="pg_dump"
            shift || true
            if [[ -n $1 ]]; then
                file="$(basename $1)"
            fi
        ;;
        "restore")
            app="pg_restore"
            shift || true
            if [[ -n $1 ]]; then
                file="$(basename $1)"
            else
                printf "You must include a filename to restore.\n"
                exit 2
            fi
        ;;
        "upgrade" | "downgrade")
            app="alembic $1"
            shift || true
            if [[ -n $1 ]]; then
                arg="$1"
            else
                arg="head"
            fi
        ;;
        *)
            printf "You have entered an invalid option\n"
            exit 2
        ;;
    esac

    shift || true
done

if [[ -z ${app} ]]; then
    printf "You did not specify the application to execute\n"
    exit 2
fi

if [[ ${app} =~ "pg_" ]]; then
    env="-e PGHOST=db -e PGDATABASE=iacode -e PGUSER=iac -e PGPASSWORD=ia-code"
    if [[ -z ${file} ]]; then
        file="iac_db_backup_$(date +%Y%m%d_%H%M%S).sqlc"
    fi

    if [[ ${app} == "pg_dump" ]]; then
        arg="-n iac -n public --blobs --format=c --file=/data/${file}"
    elif [[ ${app} == "pg_restore" ]]; then
        arg="-d iacode --if-exists -c --format=c "
        if [[ ${file} =~ \.gz$ ]]; then
            sans_gz=$(echo ${file} | sed -e 's/\.gz//g')
            arg+="/data/${sans_gz}"
        else
            arg+="/data/${file}"
        fi
    else
        printf "Invalid pg_ command\n"
        exit 1
    fi
fi

printf "Executing dbutils container\n"

if [[ ${app} == "pg_restore" && -n ${sans_gz} ]]; then
    gzip -cd ${base_path}/docker/pg_backup/${file} > ${base_path}/docker/pg_backup/${sans_gz}
fi

volumes="$(build_volumes)"

docker-compose \
    -f ${base_path}/docker/docker-compose.yml \
    -f ${base_path}/docker/docker-compose.db.yml \
    run \
    ${volumes} \
    ${env} \
    --rm \
    dbutils ${app} ${arg}

exit_code=$?

if [[ ${app} == "pg_dump" && ${exit_code} -eq 0 ]]; then
    gzip ${base_path}/docker/pg_backup/${file}
    exit_code=$?
fi

if [[ ${app} == "pg_restore" && ${exit_code} -eq 0 && -n ${sans_gz} ]]; then
    rm -f ${base_path}/docker/pg_backup/${sans_gz}
fi

printf "dbutils exit code: %d\n" ${exit_code}

exit ${exit_code}

