# IaC Tests
## Installation

Docker and network connectivity is required to build the test Docker images.
Install standard and development requirements:

```shell
pip install -r requirements.txt
pip install -r requirements_dev.txt
```

or

```shell
pipenv install -d
```

## Execution
From the `<repo_base>/src` directory, execute:

```shell
python -m pytest
```

All tests should run. 
