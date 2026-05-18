# MDMG Noticias

A self-hosted RSS/Atom news aggregator built with Django. Fetches articles from multiple feeds, groups them by media outlet and category, and presents them in a Twitter-like timeline with infinite scroll.

## Features

- Aggregate any number of RSS/Atom feeds
- Group feeds by **media outlet** (Medio) and **category**
- Filter timeline by outlet or category
- Sort articles by fetch order (ID) or publication date
- Article retention window — old articles are deleted automatically
- Keyword blocklist per feed
- Audio/video player for podcast and multimedia feeds (lazy-loaded)
- Light / dark / system theme
- OPML import/export
- Admin panel (no Django admin site required)
- Favicon auto-detection for each outlet

## Requirements

| Dependency | Version |
|---|---|
| Python | 3.11+ |
| MySQL / MariaDB | 8.0+ / 10.6+ |
| Gunicorn | 21+ (production) |

> **Note:** The feed parser falls back to `lxml` for malformed XML. Install it with `pip install lxml` for best compatibility.

## Installation

### 1. Clone the repository

```bash
git clone https://github.com/your-user/mdmg-noticias.git
cd mdmg-noticias
```

### 2. Run the install script

```bash
bash install.sh
```

The script will:
1. Create a Python virtual environment at `../venv/`
2. Install all dependencies from `requirements.txt`
3. Create `.env` from `.env.example` and prompt you to fill it in
4. Run database migrations
5. Collect static files into `../public_html/static/`
6. Create a superuser for the admin panel

### 3. Configure `.env`

```ini
# Django
SECRET_KEY=replace-with-a-long-random-string
DEBUG=False
ALLOWED_HOSTS=yourdomain.com,www.yourdomain.com

# Database (MySQL / MariaDB)
DB_NAME=newsdb
DB_USER=newsuser
DB_PASSWORD=secret
DB_HOST=localhost
DB_PORT=3306
```

Generate a secure `SECRET_KEY`:

```bash
python -c "from django.core.management.utils import get_random_secret_key; print(get_random_secret_key())"
```

### 4. Database setup

Create the MySQL database and user before running the install script:

```sql
CREATE DATABASE newsdb CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci;
CREATE USER 'newsuser'@'localhost' IDENTIFIED BY 'secret';
GRANT ALL PRIVILEGES ON newsdb.* TO 'newsuser'@'localhost';
FLUSH PRIVILEGES;
```

## Running in development

```bash
source ../venv/bin/activate
python manage.py runserver
```

Open [http://localhost:8000](http://localhost:8000) — admin panel at [http://localhost:8000/panel/](http://localhost:8000/panel/).

## Production deployment

### Gunicorn

Create `scripts/gunicorn_start.sh`:

```bash
#!/bin/bash
source /path/to/venv/bin/activate
cd /path/to/newsproject
exec gunicorn \
  --workers 3 \
  --bind unix:/path/to/gunicorn.sock \
  --daemon \
  --log-file /path/to/logs/gunicorn.log \
  config.wsgi:application
```

Add to crontab to start on reboot:

```
@reboot /path/to/scripts/gunicorn_start.sh
```

### Apache (reverse proxy)

```apache
<VirtualHost *:443>
    ServerName yourdomain.com

    ProxyPass /static/ /path/to/public_html/static/
    ProxyPassMatch "^/static/(.*)$" "!"
    Alias /static/ /path/to/public_html/static/

    ProxyPass / unix:/path/to/gunicorn.sock|http://localhost/
    ProxyPassReverse / http://localhost/

    RequestHeader set X-Forwarded-Proto "https"
</VirtualHost>
```

## Cron jobs

Add these lines to your crontab (`crontab -e`):

```cron
# Fetch new articles every 30 minutes
*/30 * * * * /path/to/venv/bin/python /path/to/newsproject/manage.py fetch_feeds >> /path/to/logs/fetch_feeds.log 2>&1

# Delete articles older than the retention window every day at 3 AM
0 3 * * * /path/to/venv/bin/python /path/to/newsproject/manage.py cleanup_articles >> /path/to/logs/cleanup_articles.log 2>&1
```

The retention window (default: 15 days) is configurable from the admin panel under **Settings**.

## Management commands

| Command | Description |
|---|---|
| `manage.py fetch_feeds` | Fetch all active feeds now |
| `manage.py fetch_feeds --batch-size N` | Fetch only the first N feeds |
| `manage.py fetch_feeds --offset N` | Start fetching from feed index N |
| `manage.py cleanup_articles` | Delete articles older than the retention window |

## Project structure

```
newsproject/
├── config/               # Django project settings and URL routing
│   ├── settings.py
│   ├── urls.py
│   └── wsgi.py
├── feeds/                # Main application
│   ├── management/
│   │   └── commands/
│   │       ├── fetch_feeds.py      # RSS fetcher
│   │       └── cleanup_articles.py # Article pruner
│   ├── migrations/       # Database migrations
│   ├── static/           # CSS, images, JS
│   ├── templates/        # HTML templates
│   ├── models.py         # Article, Feed, Medio, Category, SiteConfig
│   ├── views.py          # Public and admin views
│   ├── utils.py          # Feed fetching and parsing utilities
│   └── forms.py          # Admin panel forms
├── .env.example          # Environment variable template
├── install.sh            # Automated installation script
├── manage.py
└── requirements.txt
```

## License

MIT
