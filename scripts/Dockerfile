#-------------------------------------------------------------------------------
#
# The purpose of this Dockerfile is to delete old files from the export app
#
# Commands use to build and push:
#
# docker buildx create --use
# docker buildx build --platform linux/amd64,linux/arm64 -t rnacentral/cleanup:latest --push .
#
#-------------------------------------------------------------------------------

FROM alpine:latest

# install findutils
RUN apk --no-cache add findutils

# add the cleanup script
COPY cleanup.sh /usr/local/bin/cleanup.sh

# make the script executable
RUN chmod +x /usr/local/bin/cleanup.sh

# run the script
CMD ["/usr/local/bin/cleanup.sh"]
