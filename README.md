# DRAT - Design Recovery Automation Technology

See [this white paper](https://resources.sei.cmu.edu/library/asset-view.cfm?assetID=539327) for information about the project.


# Getting Started - alembic migrations
## Initial configuration

There is a shell script in the base of the repo called `dbutil.sh`.  It will handle the db migrations inside of a Docker container.

Initialize (build) dbutils container image (requires realpath to be installed via brew/apt/yum)

```shell
$ ./dbutil.sh build
```

Configure (if needed) and upgrade database schema to the newest revision
```shell
$ ./dbutil.sh upgrade
```

Remove schema and delete all IaC data
```shell
$ ./dbutil.sh downgrade base
```

## Alembic information

Upgrade command: `alembic upgrade head`

Output
```shell
$ alembic upgrade head
INFO  [alembic.runtime.migration] Context impl PostgresqlImpl.
INFO  [alembic.runtime.migration] Will assume transactional DDL.
INFO  [alembic.runtime.migration] Running upgrade  -> 9e36e49ea83a, baseline_c1af690
```
## Add schema change

First, add the table change to `db/tables.py`.

Then, create the revision with alembic:

```shell
$ alembic revision --autogenerate -m"Add app_info table to hold JSON data blobs"
```
Output:
```
INFO  [alembic.runtime.migration] Context impl PostgresqlImpl.
INFO  [alembic.runtime.migration] Will assume transactional DDL.
INFO  [alembic.autogenerate.compare] Detected added table 'app_infomation'
INFO  [alembic.ddl.postgresql] Detected sequence named 'patches_patch_id_seq' as owned by integer column 'patches(patch_id)', assuming SERIAL and omitting
INFO  [alembic.ddl.postgresql] Detected sequence named 'rpm_detail_rpm_detail_id_seq' as owned by integer column 'rpm_detail(rpm_detail_id)', assuming SERIAL and omitting
INFO  [alembic.ddl.postgresql] Detected sequence named 'rpm_file_detail_link_rpm_file_detail_link_id_seq' as owned by integer column 'rpm_file_detail_link(rpm_file_detail_link_id)', assuming SERIAL and omitting
INFO  [alembic.ddl.postgresql] Detected sequence named 'rpm_patch_detail_link_rpm_patch_detail_link_id_seq' as owned by integer column 'rpm_patch_detail_link(rpm_patch_detail_link_id)', assuming SERIAL and omitting
  Generating /Users/djreynolds/repo/iac-code/src/migration/versions/d3ea201ef483_add_app_info_table_to_hold_json_data_.py ... done
```

Upgrade the database (migrate the changes):

```shell
$ alembic upgrade head
```
Output:
```
INFO  [alembic.runtime.migration] Context impl PostgresqlImpl.
INFO  [alembic.runtime.migration] Will assume transactional DDL.
INFO  [alembic.runtime.migration] Running upgrade 9e36e49ea83a -> d3ea201ef483, Add app_info table to hold JSON data blobs
```

Finally, commit the changes to git:
```
git add migration/versions/d3ea201ef483_add_app_info_table_to_hold_json_data_.py
```

Rinse..repeat!

#Running DRAT

Pull the repository. All relative paths are from the repository root.
## Check your Python config
We used Python 3.6.3 and 3.6.5.  Any minor 3.6 version should work without issue.

```shell
$ pip install -r requirements.txt
```

Additionally, pipenv can be used to create an environment.
```shell
$ cd src
$ pipenv install
```

## Start the database and RPM matcher containers
Start a shell.

Clear out any dreck from the database container.

```shell
$ docker rm iac_postgres
$ docker volume rm docker_db-datavol
```

And then restart it

```shell
$ cd docker
$ docker-compose up
```

If you need to access the database:

```shell
$ psql -h localhost -p 5432 -U iac -d iacode
ia-code
```

## Prepare the database schema
Start a shell.

```shell
$ ./dbutil.sh downgrade base
$ ./dbutil.sh upgrade
```

## Create a configuration file
This file provides the connection parameters for each system to process. See `systems.conf` for an example. A couple of gotcha's:

* If you don't specify a private key, the default is ~/.ssh/id_rsa
* If you do specify a private key, use the full path, eg. ./private_key, and don't use ~ for your home directory.
* The -n argument is a host name for the system. The final 'name' argument is the friendly name for the system, which must be unique in your database and must be a legal file name string.
* Beware of trailing whitespace after the system 'name'

## Run DRAT
Start a shell.

```shell
./main.py <your_config_file_name>
```

DRAT runs in several phases:

1. Gather - connects to each system and walks through the remote file system. For each remote system, the results are saved in two files on the local directory: <system>_files.txt and <system>_packages.txt.

1. Load - reads the files from the local file system and populates the database. Files installed by packages are marked.

1. Analysis - Gets the changed file contents, and runs the heuristic rules.

1. Generate IaC - Creates Ansible files to deploy a new copy of each system.

## Running test suite
1. Start a shell and go to `<repo_directory>/iac-code/src`
2. Install development dependencies with `pipenv install --dev` or `pip install -r requirements_dev.txt`
3. Execute the following from the src directory:

```shell
cd iac-code/src
python -m pytest
```
