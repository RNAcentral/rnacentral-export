# rnacentral-export

Microservice to export RNAcentral data

## Installation

1. Clone Git repository:

  ```
  git clone https://github.com/RNAcentral/rnacentral-export.git
  ```

2. Run the app using [Docker](https://www.docker.com):

  ```
  docker-compose up --build
  ```

## Tests

To run unit tests, use

  ```
  docker exec rnacentral-export_web_1 pytest ./app/tests.py
  ```