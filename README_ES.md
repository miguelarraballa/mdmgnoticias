# MDMG Noticias

Agregador de noticias RSS/Atom autoalojado construido con Django. Obtiene artículos de múltiples fuentes, los agrupa por medio de comunicación y categoría, y los presenta en una línea de tiempo estilo Twitter con scroll infinito.

## Características

- Agrega cualquier número de fuentes RSS/Atom
- Agrupa las fuentes por **medio de comunicación** (Medio) y **categoría**
- Filtra la línea de tiempo por medio o categoría
- Ordena los artículos por orden de obtención (ID) o fecha de publicación
- Ventana de retención de artículos — los artículos antiguos se eliminan automáticamente
- Lista de palabras clave bloqueadas por fuente
- Reproductor de audio/vídeo para fuentes de podcast y multimedia (carga diferida)
- Tema claro / oscuro / del sistema
- Importación/exportación OPML
- Panel de administración (sin necesidad del admin de Django)
- Detección automática de favicon para cada medio

## Requisitos

| Dependencia | Versión |
|---|---|
| Python | 3.11+ |
| MySQL / MariaDB | 8.0+ / 10.6+ |
| Gunicorn | 21+ (producción) |

> **Nota:** El analizador de fuentes recurre a `lxml` para XML mal formado. Instálalo con `pip install lxml` para mayor compatibilidad.

## Instalación

### 1. Clonar el repositorio

```bash
git clone https://github.com/your-user/mdmg-noticias.git
cd mdmg-noticias
```

### 2. Ejecutar el script de instalación

```bash
bash install.sh
```

El script realizará lo siguiente:
1. Crear un entorno virtual de Python en `../venv/`
2. Instalar todas las dependencias de `requirements.txt`
3. Crear `.env` a partir de `.env.example` y solicitarte que lo rellenes
4. Ejecutar las migraciones de base de datos
5. Recopilar los ficheros estáticos en `../public_html/static/`
6. Crear un superusuario para el panel de administración

### 3. Configurar `.env`

```ini
# Django
SECRET_KEY=reemplaza-con-una-cadena-larga-y-aleatoria
DEBUG=False
ALLOWED_HOSTS=tudominio.com,www.tudominio.com

# Base de datos (MySQL / MariaDB)
DB_NAME=newsdb
DB_USER=newsuser
DB_PASSWORD=secreto
DB_HOST=localhost
DB_PORT=3306
```

Genera una `SECRET_KEY` segura:

```bash
python -c "from django.core.management.utils import get_random_secret_key; print(get_random_secret_key())"
```

### 4. Configuración de la base de datos

Crea la base de datos y el usuario MySQL antes de ejecutar el script de instalación:

```sql
CREATE DATABASE newsdb CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci;
CREATE USER 'newsuser'@'localhost' IDENTIFIED BY 'secreto';
GRANT ALL PRIVILEGES ON newsdb.* TO 'newsuser'@'localhost';
FLUSH PRIVILEGES;
```

## Ejecución en desarrollo

```bash
source ../venv/bin/activate
python manage.py runserver
```

Abre [http://localhost:8000](http://localhost:8000) — panel de administración en [http://localhost:8000/panel/](http://localhost:8000/panel/).

## Despliegue en producción

### Gunicorn

Crea `scripts/gunicorn_start.sh`:

```bash
#!/bin/bash
source /ruta/al/venv/bin/activate
cd /ruta/al/newsproject
exec gunicorn \
  --workers 3 \
  --bind unix:/ruta/al/gunicorn.sock \
  --daemon \
  --log-file /ruta/al/logs/gunicorn.log \
  config.wsgi:application
```

Añade al crontab para iniciarlo al arrancar el sistema:

```
@reboot /ruta/al/scripts/gunicorn_start.sh
```

### Apache (proxy inverso)

```apache
<VirtualHost *:443>
    ServerName tudominio.com

    ProxyPass /static/ /ruta/al/public_html/static/
    ProxyPassMatch "^/static/(.*)$" "!"
    Alias /static/ /ruta/al/public_html/static/

    ProxyPass / unix:/ruta/al/gunicorn.sock|http://localhost/
    ProxyPassReverse / http://localhost/

    RequestHeader set X-Forwarded-Proto "https"
</VirtualHost>
```

## Tareas programadas (cron)

Añade estas líneas a tu crontab (`crontab -e`):

```cron
# Obtener nuevos artículos cada 30 minutos
*/30 * * * * /ruta/al/venv/bin/python /ruta/al/newsproject/manage.py fetch_feeds >> /ruta/al/logs/fetch_feeds.log 2>&1

# Eliminar artículos más antiguos que la ventana de retención todos los días a las 3 AM
0 3 * * * /ruta/al/venv/bin/python /ruta/al/newsproject/manage.py cleanup_articles >> /ruta/al/logs/cleanup_articles.log 2>&1
```

La ventana de retención (por defecto: 15 días) es configurable desde el panel de administración en **Ajustes**.

## Comandos de gestión

| Comando | Descripción |
|---|---|
| `manage.py fetch_feeds` | Obtiene todas las fuentes activas ahora mismo |
| `manage.py fetch_feeds --batch-size N` | Obtiene solo las primeras N fuentes |
| `manage.py fetch_feeds --offset N` | Empieza a obtener desde el índice de fuente N |
| `manage.py cleanup_articles` | Elimina los artículos más antiguos que la ventana de retención |

## Estructura del proyecto

```
newsproject/
├── config/               # Configuración del proyecto Django y enrutamiento de URLs
│   ├── settings.py
│   ├── urls.py
│   └── wsgi.py
├── feeds/                # Aplicación principal
│   ├── management/
│   │   └── commands/
│   │       ├── fetch_feeds.py      # Obtenedor de RSS
│   │       └── cleanup_articles.py # Limpiador de artículos
│   ├── migrations/       # Migraciones de base de datos
│   ├── static/           # CSS, imágenes, JS
│   ├── templates/        # Plantillas HTML
│   ├── models.py         # Article, Feed, Medio, Category, SiteConfig
│   ├── views.py          # Vistas públicas y de administración
│   ├── utils.py          # Utilidades de obtención y análisis de fuentes
│   └── forms.py          # Formularios del panel de administración
├── .env.example          # Plantilla de variables de entorno
├── install.sh            # Script de instalación automatizada
├── manage.py
└── requirements.txt
```

## Licencia

MIT
