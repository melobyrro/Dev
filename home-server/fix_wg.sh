#!/bin/bash
sudo ufw allow from 10.13.13.0/24
sed -i 's/0.0.0.0\/0,::\/0/0.0.0.0\/0/' /home/byrro/docker/wireguard/docker-compose.yml
sed -i '/net.ipv6.conf.all.forwarding=1/d' /home/byrro/docker/wireguard/docker-compose.yml
cd /home/byrro/docker/wireguard
docker compose up -d --force-recreate
