# 🐳 Docker Setup Guide

Complete guide to run the Chat Application using Docker.

---

## 📋 Prerequisites

- **Docker Desktop** installed
  - Windows: [Download Docker Desktop](https://www.docker.com/products/docker-desktop/)
  - Make sure Docker Desktop is running

---

## 🚀 Quick Start

### 1. Open Command Prompt

```cmd
cd C:\Users\sunda\Documents\Chat_Django
```

### 2. Build and Start Containers

```cmd
docker-compose up --build
```

This command will:
- ✅ Download PostgreSQL image
- ✅ Download Redis image
- ✅ Build Django application
- ✅ Create database tables
- ✅ Start all services

### 3. Open Application

Open browser: **http://localhost:8000**

---

## 🎯 Docker Commands

### Start Services
```cmd
docker-compose up
```

### Start in Background (Detached Mode)
```cmd
docker-compose up -d
```

### Stop Services
```cmd
docker-compose down
```

### View Logs
```cmd
docker-compose logs -f
```

### View Specific Service Logs
```cmd
docker-compose logs -f web
```

### Restart Services
```cmd
docker-compose restart
```

### Rebuild (After Code Changes)
```cmd
docker-compose up --build
```

---

## 📦 Services Running

| Service | Container Name | Port | Purpose |
|---------|---------------|------|---------|
| **PostgreSQL** | chat_db | 5432 | Database |
| **Redis** | chat_redis | 6379 | Real-time messaging |
| **Django** | chat_backend | 8000 | Web application |

---

## 🔧 Useful Commands

### Access Django Shell
```cmd
docker-compose exec web python manage.py shell
```

### Create Superuser
```cmd
docker-compose exec web python manage.py createsuperuser
```

### Run Migrations
```cmd
docker-compose exec web python manage.py migrate
```

### Access Database
```cmd
docker-compose exec db psql -U postgres -d chat_db
```

### Access Redis CLI
```cmd
docker-compose exec redis redis-cli
```

### View Container Status
```cmd
docker-compose ps
```

---

## 🗂 Docker Architecture

```
┌─────────────────────────────────────────┐
│         Docker Host (Your PC)           │
│                                         │
│  ┌───────────┐  ┌────────┐  ┌───────┐ │
│  │  Django   │  │ Postgre│  │ Redis │ │
│  │   :8000   │  │  :5432 │  │ :6379 │ │
│  └─────┬─────┘  └────┬───┘  └───┬───┘ │
│        │             │           │     │
│        └─────────────┴───────────┘     │
│              chat_network              │
└─────────────────────────────────────────┘
```

---

## 📁 Files Created

| File | Purpose |
|------|---------|
| `Dockerfile` | Django app container instructions |
| `docker-compose.yml` | Multi-container orchestration |
| `.dockerignore` | Files to exclude from Docker build |

---

## 🔐 Environment Variables

Default values in `docker-compose.yml`:

```yaml
- DEBUG=True
- SECRET_KEY=django-insecure-change-this-in-production-12345
- DB_NAME=chat_db
- DB_USER=postgres
- DB_PASSWORD=postgres123
- DB_HOST=db
- DB_PORT=5432
- REDIS_HOST=redis
```

**⚠️ Important:** Change these values for production!

---

## 📊 Data Persistence

Docker volumes ensure data persists even after container restart:

| Volume | Stores |
|--------|--------|
| `postgres_data` | Database files |
| `redis_data` | Redis cache |
| `media_data` | Uploaded files |
| `static_data` | Static CSS/JS files |

---

## 🛠 Troubleshooting

### Problem: Port Already in Use

**Error:** `Bind for 0.0.0.0:8000 failed: port is already allocated`

**Solution:**
```cmd
# Stop running services
docker-compose down

# Or change port in docker-compose.yml
ports:
  - "8080:8000"  # Use 8080 instead
```

---

### Problem: Database Connection Failed

**Solution:**
```cmd
# Check if database is healthy
docker-compose ps

# Restart database
docker-compose restart db

# View database logs
docker-compose logs db
```

---

### Problem: Changes Not Reflected

**Solution:**
```cmd
# Rebuild containers
docker-compose up --build

# Or rebuild specific service
docker-compose build web
docker-compose up web
```

---

### Problem: Permission Denied (Windows)

**Solution:**
- Make sure Docker Desktop is running
- Run Command Prompt as Administrator
- Enable file sharing in Docker Desktop settings

---

## 🧹 Clean Up

### Remove All Containers and Images
```cmd
docker-compose down --rmi all
```

### Remove Volumes (Deletes Data!)
```cmd
docker-compose down -v
```

### Complete Clean
```cmd
docker-compose down -v --rmi all
docker system prune -a
```

---

## 🌐 Production Deployment

### 1. Update Environment Variables

Create `.env.production`:
```env
DEBUG=False
SECRET_KEY=your-super-secret-production-key-here
DB_PASSWORD=strong-password-here
ALLOWED_HOSTS=yourdomain.com,www.yourdomain.com
```

### 2. Update docker-compose.yml

```yaml
web:
  environment:
    - DEBUG=False
  env_file:
    - .env.production
```

### 3. Use Production Server

Replace Daphne command with Gunicorn + Daphne:
```yaml
command: >
  sh -c "gunicorn chat_project.wsgi:application --bind 0.0.0.0:8000 &
         daphne -b 0.0.0.0 -p 8001 chat_project.asgi:application"
```

### 4. Add Nginx (Reverse Proxy)

Create `nginx/nginx.conf` and add service to `docker-compose.yml`

---

## 📊 Monitoring

### Check Resource Usage
```cmd
docker stats
```

### Check Container Health
```cmd
docker-compose ps
```

### View All Containers
```cmd
docker ps -a
```

---

## 🎓 Learning Resources

### Docker Basics
- [Docker Documentation](https://docs.docker.com/)
- [Docker Compose Tutorial](https://docs.docker.com/compose/gettingstarted/)

### Docker Commands
- [Docker CLI Reference](https://docs.docker.com/engine/reference/commandline/cli/)
- [Docker Compose CLI](https://docs.docker.com/compose/reference/)

---

## ✅ Quick Checklist

Before running Docker:

- [ ] Docker Desktop installed and running
- [ ] Project folder contains all files
- [ ] No local PostgreSQL/Redis running (port conflict)
- [ ] Enough disk space (~2GB)

After starting Docker:

- [ ] All containers are running: `docker-compose ps`
- [ ] Database is healthy (showing "healthy" status)
- [ ] Application accessible at http://localhost:8000
- [ ] Can register and login

---

## 🆘 Getting Help

### Check Logs
```cmd
# All services
docker-compose logs

# Specific service
docker-compose logs web
docker-compose logs db
docker-compose logs redis

# Follow logs (real-time)
docker-compose logs -f web
```

### Inspect Container
```cmd
docker-compose exec web bash
```

### Check Network
```cmd
docker network ls
docker network inspect chat_network
```

---

## 🎉 Success!

If you see this when you run `docker-compose ps`:

```
NAME                STATUS              PORTS
chat_backend        Up (healthy)        0.0.0.0:8000->8000/tcp
chat_db             Up (healthy)        0.0.0.0:5432->5432/tcp
chat_redis          Up (healthy)        0.0.0.0:6379->6379/tcp
```

**Congratulations! Your application is running! 🚀**

Visit: **http://localhost:8000**

---

## 📝 Notes

- Docker Desktop must be running before executing commands
- First build takes 5-10 minutes (downloads images)
- Subsequent builds are much faster
- Data persists in Docker volumes
- Can run alongside local development

---

**Happy Dockerizing! 🐳**