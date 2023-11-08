FROM debian:stable-slim

# Define environment variables
ENV DEBIAN_FRONTEND=noninteractive
ENV SHELL=/bin/bash

# Set the working directory to /root
WORKDIR /root

# Copy required files
COPY files/* /root/
COPY files/rspamd_config/* /root/rspamd_config/

# Install required software
RUN apt-get update && \
    apt-get install -y --no-install-recommends \
      cron \
      nano \
      python3 \
      python3-pip \
      python3-setuptools \
      rsyslog \
      unzip \
      wget \
      python3-sphinx \
      lighttpd \
      logrotate \
      gnupg \
      unattended-upgrades && \
    # Clean up APT when done.
    apt-get clean && \
    rm -rf /var/lib/apt/lists/*

# Install dependencies for pushtest
RUN pip3 install imapclient --break-system-packages

# Download and install irsd (as long as it is not pushed to pypi)
RUN pip3 install --upgrade setuptools  --break-system-packages
RUN wget https://codeberg.org/antispambox/IRSD/archive/master.zip && \
    unzip master.zip && \
    cd irsd && \
    python3 setup.py install && \
    cd .. && \
    rm -Rf irsd master.zip

# Install IP2Location
RUN pip3 install IP2Location --break-system-packages && \
    wget https://download.ip2location.com/lite/IP2LOCATION-LITE-DB1.BIN.ZIP && \
    wget https://download.ip2location.com/lite/IP2LOCATION-LITE-DB1.IPV6.BIN.ZIP && \
    unzip -o IP2LOCATION-LITE-DB1.BIN.ZIP && \
    unzip -o IP2LOCATION-LITE-DB1.IPV6.BIN.ZIP && \
    rm *.ZIP

############################
# Configure software
############################

# Create necessary directories and configure cron, logrotate, and timezone
RUN mkdir /root/accounts && \
    crontab /root/cron_configuration && \
    rm /root/cron_configuration && \
    mv mailreport_logrotate /etc/logrotate.d/mailreport_logrotate && \
    echo "alias logger='/usr/bin/logger -e'" >> /etc/bash.bashrc && \
    echo "LANG=en_US.UTF-8" > /etc/default/locale && \
    ln -sf /usr/share/zoneinfo/Europe/Berlin /etc/localtime && \
    ln -sf /usr/share/zoneinfo/Europe/Berlin /etc/timezone

# Install rspamd
RUN CODENAME=$(lsb_release -c -s) && \
    echo "deb [arch=amd64] http://rspamd.com/apt-stable/ $CODENAME main" > /etc/apt/sources.list.d/rspamd.list && \
    wget -O- https://rspamd.com/apt-stable/gpg.key | apt-key add - && \
    apt-get update && \
    apt-get --no-install-recommends install -y rspamd redis-server && \
    sed -i 's+/var/lib/redis+/var/spamassassin/bayesdb+' /etc/redis/redis.conf && \
    cp /root/rspamd_config/* /etc/rspamd/local.d/ && \
    rm -r /root/rspamd_config && \
    # Clean up APT when done.
    apt-get clean && \
    rm -rf /var/lib/apt/lists/*

# Define volumes
VOLUME /var/spamassassin/bayesdb
VOLUME /root/accounts

# Expose the rspamd port
EXPOSE 11334/tcp

# Define the command to run when starting the container
CMD ["sh", "-c", "python3 /root/startup.py && tail -n 0 -F /var/log/*.log"]
