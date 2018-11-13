# Defines a container for the Keystone META monitor.
# Usage:
#   $ docker build . -t keystone-metamon \
#       --build-arg SECRET_URL=<secret_url> \
#       --build-arg KMS_PROJECT=<kms_project> \
#       --build-arg KMS_KEYRING=<kms_keyring> \
#       --build-arg KMS_KEY=<kms_key>
#   $ docker run keystone-metamon

FROM ubuntu:18.04

# Install dependencies from the package manager.
#   - git: Access META repositories
#   - python: Dependency for Google Cloud command line client
#   - python3: Dependency for META monitor service
#   - python3-pip: Install required python library dependencies
#   - wget: Fetch Google Cloud command line client
RUN apt update && \
    apt install -y \
    git \
    python \
    python3 \
    python3-pip \
    wget

# Google Cloud SDK installation command borrowed from...
# https://github.com/pivotal-cf/bosh-concourse-deployments/blob/master/docker/Dockerfile
ENV GCLOUD_SDK_VERSION=218.0.0
RUN wget -q -O /usr/gcloud.tar.gz https://dl.google.com/dl/cloudsdk/channels/rapid/downloads/google-cloud-sdk-$GCLOUD_SDK_VERSION-linux-x86_64.tar.gz && \
    ( \
      echo 'd6b59e12dec1bff384118e154e5bdceea40f8820a515bd54c26e6a5acfafeb7b' /usr/gcloud.tar.gz | \
      sha256sum -c - \
    ) && \
    tar -C /usr/ -xzf /usr/gcloud.tar.gz && \
    /usr/google-cloud-sdk/install.sh --usage-reporting false --path-update false --command-completion false -q && \
    rm /usr/gcloud.tar.gz

# Python dependencies installed from PIP.
#   - google-api-python-client: Client library for Google Cloud
#   - google-cloud-logging: Client library for logging to StackDriver
RUN pip3 install \
    google-api-python-client \
    google-cloud-logging

# Remove transient dependencies.
RUN apt remove -y \
    wget
RUN apt autoremove -y

# META monitor service scripts.
COPY meta_monitor_gce.py /usr/sbin/meta_monitor_gce.py
COPY meta_monitor.py /usr/sbin/meta_monitor.py
COPY run.sh /usr/sbin/run.sh

# Parameters for fetching and decrypting secrets when the container is run.
# There should be no secret information contained in these arguments per se,
# rather they are passed as arguments to gcloud commands that fetch and decrypt
# the actual secrets.
ARG SECRET_URL
ARG KMS_PROJECT
ARG KMS_KEYRING
ARG KMS_KEY

ENV SECRET_URL=${SECRET_URL}
ENV KMS_PROJECT=${KMS_PROJECT}
ENV KMS_KEYRING=${KMS_KEYRING}
ENV KMS_KEY=${KMS_KEY}
ENV WORK_DIR="/tmp"

# Run the META monitor service by default.
ENTRYPOINT bash /usr/sbin/run.sh $SECRET_URL $KMS_PROJECT $KMS_KEYRING $KMS_KEY
