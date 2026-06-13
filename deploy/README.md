# Linux 部署指南（Nginx Virtual Host + Gunicorn WSGI）

本專案以 **Linux** 為目標執行環境，透過 **Nginx** 作為反向代理與靜態檔服務，並以 **Gunicorn** 透過 **WSGI** 執行 Django Application。

## 架構

```
Client → Nginx (Virtual Host :80/:443)
           ├─ /static/  → 專案 staticfiles
           ├─ /media/   → 專案 media
           └─ /         → Gunicorn (unix socket) → mysite.wsgi:application
```

## 前置需求

- Ubuntu 22.04+ / Debian 12+（或其他 Linux 發行版）
- Python 3.11+
- MariaDB 或 MySQL 8+
- Redis（Celery 背景任務，可選）
- Nginx
- 系統使用者 `eatwhat`（建議）

## 1. 安裝系統套件

```bash
sudo apt update
sudo apt install -y python3-venv python3-dev build-essential \
  nginx mariadb-server redis-server \
  libmariadb-dev pkg-config
```

## 2. 建立虛擬環境與安裝依賴

```bash
sudo useradd -r -m -d /srv/eatwhat eatwhat || true
sudo mkdir -p /srv/eatwhat/app
sudo chown -R eatwhat:eatwhat /srv/eatwhat

sudo -u eatwhat bash -c '
  cd /srv/eatwhat/app
  python3 -m venv .venv
  source .venv/bin/activate
  pip install -r requirements.txt
'
```

## 3. 環境變數

```bash
sudo cp /srv/eatwhat/app/.env.example /srv/eatwhat/app/.env
sudo nano /srv/eatwhat/app/.env
```

正式環境至少設定：

```env
DEBUG=false
SECRET_KEY=<強隨機字串>
ALLOWED_HOSTS=your.domain.com,www.your.domain.com
DB_ENGINE=django.db.backends.mysql
DB_NAME=eat_what
DB_USER=eatwhat
DB_PASSWORD=<密碼>
DB_HOST=127.0.0.1
DB_PORT=3306
```

## 4. 資料庫與靜態檔

```bash
sudo -u eatwhat bash -c '
  cd /srv/eatwhat/app
  source .venv/bin/activate
  python manage.py migrate
  python manage.py collectstatic --noinput
'
```

## 5. Gunicorn（WSGI）

```bash
sudo cp deploy/systemd/eatwhat.service /etc/systemd/system/
sudo cp deploy/gunicorn/gunicorn.conf.py /srv/eatwhat/app/deploy/gunicorn/
# 若專案路徑不同，請編輯 eatwhat.service 內 WorkingDirectory / EnvironmentFile

sudo systemctl daemon-reload
sudo systemctl enable eatwhat
sudo systemctl start eatwhat
sudo systemctl status eatwhat
```

Gunicorn 直接載入 `mysite.wsgi:application`（見 `mysite/wsgi.py`）。

## 6. Nginx Virtual Host

```bash
sudo cp deploy/nginx/eatwhat.conf /etc/nginx/sites-available/eatwhat.conf
sudo ln -sf /etc/nginx/sites-available/eatwhat.conf /etc/nginx/sites-enabled/
# 修改 server_name、ssl_certificate（若使用 HTTPS）
sudo nginx -t
sudo systemctl reload nginx
```

## 7. Celery Worker（可選）

```bash
sudo cp deploy/systemd/eatwhat-celery.service /etc/systemd/system/
sudo systemctl enable eatwhat-celery
sudo systemctl start eatwhat-celery
```

## 檔案說明

| 檔案 | 用途 |
|------|------|
| `deploy/nginx/eatwhat.conf` | Nginx Virtual Host |
| `deploy/gunicorn/gunicorn.conf.py` | Gunicorn WSGI 設定 |
| `deploy/systemd/eatwhat.service` | Gunicorn systemd 服務 |
| `deploy/systemd/eatwhat-celery.service` | Celery worker 服務 |

## 驗證

```bash
curl -I http://your.domain.com/
curl -I http://your.domain.com/api/v1/posts/
```
