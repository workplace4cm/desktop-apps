# A stock Ubuntu desktop: the package set of the official desktop ISO (the
# packages a container can hold), plus the tools the release checks drive the
# applications with. The release workflow runs it with --network none, so
# the Secure Office Suite package is installed and used with no network.
ARG UBUNTU=24.04
FROM ubuntu:${UBUNTU}
ARG UBUNTU
ENV DEBIAN_FRONTEND=noninteractive
COPY stock-desktop.sh /stock-desktop.sh
RUN bash /stock-desktop.sh "$UBUNTU"
