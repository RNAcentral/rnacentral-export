# create image to export requirements
FROM python:3.11-slim-bullseye AS poetry

# build dependencies
RUN apt-get update \
    && apt-get install --no-install-recommends -y \
        build-essential \
        gcc \
    && apt-get autoremove -y \
    && apt-get clean -y \
    && rm -rf /var/lib/apt/lists/*

# ARG for dev dependencies
ARG DEV=false

# install poetry
RUN python -m pip install --no-cache-dir --upgrade poetry==1.8.2

# copy dependencies
COPY poetry.lock pyproject.toml ./

# create a requirements file conditionally including dev dependencies
RUN if [ "$DEV" = "true" ]; then \
        poetry export -f requirements.txt --without-hashes --with dev -o /tmp/requirements.txt; \
    else \
        poetry export -f requirements.txt --without-hashes -o /tmp/requirements.txt; \
    fi

# create rnacentral-export image
FROM python:3.11-slim-bullseye as rnacentral-export

ENV \
    PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    HOME="/srv/rnacentral-export" \
    LOCAL="/srv/local"

# build dependencies
RUN apt-get update \
    && apt-get install --no-install-recommends -y \
        g++ \
        build-essential \
        curl \
        tar \
    && apt-get autoremove -y \
    && apt-get clean -y \
    && rm -rf /var/lib/apt/lists/*

# create folders
RUN \
    mkdir $HOME && \
    mkdir $LOCAL && \
    mkdir /srv/results && \
    mkdir /srv/logs

# install Infernal
RUN \
    cd $LOCAL && \
    curl -OL http://eddylab.org/infernal/infernal-1.1.5-macosx-silicon.tar.gz && \
    tar -xvzf infernal-1.1.5-macosx-silicon.tar.gz && \
    cd infernal-1.1.5-macosx-silicon && \
    ./configure --prefix=$LOCAL/infernal-1.1.5 && \
    make && \
    make install && \
    cd easel && \
    make install && \
    cd $LOCAL && \
    rm infernal-1.1.5-macosx-silicon.tar.gz

# create user
RUN useradd -m -d $HOME -s /bin/bash rnacentral

# set work directory
WORKDIR $HOME

# install requirements
COPY --from=poetry /tmp/requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# copy project
COPY . .
RUN chown -R rnacentral:rnacentral /srv

# set user
USER rnacentral

# run the FastAPI app
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
