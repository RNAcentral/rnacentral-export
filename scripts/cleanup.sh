#!/bin/sh

# find and delete files older than 7 days
find /srv/results/ -type f -mtime +7 -exec rm -f {} \;
