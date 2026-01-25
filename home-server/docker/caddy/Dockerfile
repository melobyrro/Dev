FROM caddy:builder AS builder
RUN xcaddy build     --with github.com/caddy-dns/cloudflare@latest     --with github.com/caddyserver/replace-response@latest     --replace github.com/smallstep/certificates=github.com/smallstep/certificates@v0.29.0

FROM caddy:latest
COPY --from=builder /usr/bin/caddy /usr/bin/caddy
