FROM lscr.io/linuxserver/plex:latest

# Add Intel VAAPI driver + vainfo for debugging.
RUN apt-get update  && apt-get install -y --no-install-recommends       intel-media-va-driver       vainfo  && rm -rf /var/lib/apt/lists/*

ENV LIBVA_DRIVERS_PATH=/usr/lib/x86_64-linux-gnu/dri
ENV LIBVA_DRIVER_NAME=iHD
