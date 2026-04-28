# Janus Web Application
Modern reactive WebUI for user-driven DTN endpoint provisioning with Janus.

## Overview
Janus Web provides a comprehensive management interface for the Janus container provisioning system. It features reactive dashboards for sessions, profiles, and endpoints, as well as unified access control management.

## Architecture
- **Backend**: Django 5.2 LTS (Python 3.10+)
- **Frontend**: Vue 3 with Vite, Pinia for state management, and Bootstrap 4 for styling.
- **Communication**: Httpx with 30s timeouts for robust controller interaction; WebSockets for real-time event proxying.

## Prerequisites
- **Python**: 3.10 or higher
- **Node.js**: 18.x or higher (for frontend development and building)
- **Janus Controller**: A running instance of the Janus Controller API.

## Local Development Setup

### 1. Backend Setup
Clone the repository and install Python dependencies:
```bash
git clone https://github.com/esnet/janus-web.git
cd janus-web
pip install -r requirements.txt
```

Initialize the local SQLite database:
```bash
cd webapp
python manage.py migrate
python manage.py createsuperuser
```

### 2. Frontend Setup
Install Node.js dependencies:
```bash
cd ..  # Back to project root
npm install
```

### 3. Running for Development
For the best experience (including Hot Module Replacement), run both the Vite dev server and the Django backend:

**Terminal 1: Vite Dev Server**
```bash
npm run dev -- --host 127.0.0.1 --port 3000
```

**Terminal 2: Django Backend**
```bash
cd webapp
# Point to your Janus Controller (e.g., port 5000)
export JANUS_WEB_CTRL_HOST=127.0.0.1
export JANUS_WEB_CTRL_PORT=5000
export CTRL_HTTP_PROTOCOL=http
export CTRL_WS_PROTOCOL=ws
python manage.py runserver 0.0.0.0:8080
```

Access the UI at `http://127.0.0.1:8080`.

---

## Configuration
Configure the following environment variables to customize the connection to the Janus Controller and authentication:

| Variable | Description | Default |
|----------|-------------|---------|
| `JANUS_WEB_CTRL_HOST` | Hostname of the Janus Controller | `localhost` |
| `JANUS_WEB_CTRL_PORT` | Port of the Janus Controller | `5000` |
| `CTRL_HTTP_PROTOCOL` | `http` or `https` | `https` |
| `CTRL_WS_PROTOCOL` | `ws` or `wss` | `wss` |
| `CTRL_SSL_VERIFY` | Verify SSL certificates | `True` |
| `LOCAL_LOGIN_ENABLED` | Enable local username/password login | `True` |

### OIDC / SSO Setup
For production SSO, configure the following:
- `OIDC_RP_CLIENT_ID`
- `OIDC_RP_CLIENT_SECRET`

---

## Deployment

### 1. Build the Frontend
Compile the Vue 3 assets into the Django static directory:
```bash
npm run build
```
This generates optimized assets in `webapp/static/static/dist/`.

### 2. Production Static Serving
Collect all static files for your web server (e.g., Nginx):
```bash
cd webapp
python manage.py collectstatic
```

### 3. Run with Gunicorn (Example)
```bash
gunicorn webapp.wsgi:application --bind 0.0.0.0:8080
```

## Features
- **Reactive Dashboards**: Real-time status updates for Sessions and Endpoints.
- **Session Management**: Create, Edit, Start, Stop, and Reprovision sessions in-place.
- **Profile Management**: Full CRUD for Host, Network, and Volume profiles with lifecycle tracking.
- **Bulk Authorization**: Efficiently manage user/group access across multiple resources.
- **Log Viewer**: Integrated container log streaming with timestamp support.
