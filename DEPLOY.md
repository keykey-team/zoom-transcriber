# Deploy on Ubuntu VPS

## 1. DNS

Point the A record for `zoom-transcribition.keykey.com.ua` to `185.237.205.38`.

## 2. Install Docker on Ubuntu

```bash
sudo apt-get update
sudo apt-get install -y ca-certificates curl gnupg
sudo install -m 0755 -d /etc/apt/keyrings
curl -fsSL https://download.docker.com/linux/ubuntu/gpg | sudo gpg --dearmor -o /etc/apt/keyrings/docker.gpg
sudo chmod a+r /etc/apt/keyrings/docker.gpg
echo \
  "deb [arch=$(dpkg --print-architecture) signed-by=/etc/apt/keyrings/docker.gpg] https://download.docker.com/linux/ubuntu \
  $(. /etc/os-release && echo $VERSION_CODENAME) stable" | \
  sudo tee /etc/apt/sources.list.d/docker.list > /dev/null
sudo apt-get update
sudo apt-get install -y docker-ce docker-ce-cli containerd.io docker-buildx-plugin docker-compose-plugin
sudo usermod -aG docker $USER
```

Relogin after adding your user to the `docker` group.

## 3. Project setup

```bash
cd /opt
sudo git clone <YOUR_REPOSITORY_URL> zoom-transcribition
sudo chown -R $USER:$USER /opt/zoom-transcribition
cd /opt/zoom-transcribition
cp .env.example .env
```

The image installs CPU-only PyTorch. If your VPS is not powerful, change `WHISPER_MODEL` in `.env` to `small` or `base` for faster transcription.

## 4. Start containers

```bash
docker compose up -d --build
docker compose ps
docker compose logs -f backend
```

The stack publishes services only on loopback:

- frontend: `127.0.0.1:3001`
- backend: `127.0.0.1:5003`

This is intentional so public traffic goes only through host nginx.

If `docker compose up` fails with `port is already allocated`, change `FRONTEND_PORT` or `BACKEND_PORT` in `.env` to a free local port and update the matching `proxy_pass` value in nginx.

## 5. Nginx

Copy [deploy/nginx/zoom-transcribition.keykey.com.ua.conf](deploy/nginx/zoom-transcribition.keykey.com.ua.conf) to `/etc/nginx/sites-available/zoom-transcribition.keykey.com.ua` and enable it:

```bash
sudo cp deploy/nginx/zoom-transcribition.keykey.com.ua.conf /etc/nginx/sites-available/zoom-transcribition.keykey.com.ua
sudo ln -s /etc/nginx/sites-available/zoom-transcribition.keykey.com.ua /etc/nginx/sites-enabled/zoom-transcribition.keykey.com.ua
sudo nginx -t
sudo systemctl reload nginx
```

## 6. HTTPS with Certbot

```bash
sudo apt-get install -y certbot python3-certbot-nginx
sudo certbot --nginx -d zoom-transcribition.keykey.com.ua
```

Certbot will add the SSL server block and redirect HTTP to HTTPS.

## 7. Updating the app

```bash
cd /opt/zoom-transcribition
git pull
docker compose up -d --build
```
