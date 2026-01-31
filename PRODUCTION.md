# Production Deployment Guide

This guide covers deploying Kuiper TTS in a production environment.

## Pre-Deployment Checklist

### 1. Environment Configuration

1. Copy `.env.example` to `.env`:
   ```bash
   cp .env.example .env
   ```

2. Update `.env` with production settings:
   ```bash
   KUIPER_ENV=production
   KUIPER_DEBUG=false
   KUIPER_CORS_ORIGINS=https://yourdomain.com
   KUIPER_LOG_FILE=logs/kuiper.log
   ```

### 2. Security Settings

**Critical Security Configurations:**

- **CORS Origins**: Set `KUIPER_CORS_ORIGINS` to only allow your frontend domain(s)
- **Debug Mode**: Ensure `KUIPER_DEBUG=false` in production
- **Rate Limiting**: Configure `KUIPER_RATE_LIMIT` (default: 60 requests/minute)
- **File Upload Limits**: Set `KUIPER_MAX_UPLOAD_SIZE_MB` appropriately (default: 100MB)

### 3. Dependencies

Install all required dependencies:

```bash
# Backend
pip install -r backend/requirements.txt

# Frontend
cd app
npm install
npm run build
```

### 4. Directory Structure

Ensure the following directories exist and are writable:

- `recordings/` - User recordings
- `data/` - Training data and cache
- `logs/` - Application logs (if using file logging)

## Running in Production

### Option 1: Using run_server.py

```bash
# Set environment to production
export KUIPER_ENV=production

# Run server
python run_server.py --host 127.0.0.1 --port 8765
```

### Option 2: Using Uvicorn Directly

```bash
uvicorn backend.api.main:app \
  --host 127.0.0.1 \
  --port 8765 \
  --workers 4 \
  --log-level info
```

### Option 3: Using a Process Manager (systemd)

Create `/etc/systemd/system/kuiper-tts.service`:

```ini
[Unit]
Description=Kuiper TTS API Server
After=network.target

[Service]
Type=simple
User=kuiper
WorkingDirectory=/path/to/Train_TTS_Application
Environment="KUIPER_ENV=production"
Environment="KUIPER_LOG_FILE=/var/log/kuiper/kuiper.log"
ExecStart=/usr/bin/python3 /path/to/Train_TTS_Application/run_server.py
Restart=always
RestartSec=10

[Install]
WantedBy=multi-user.target
```

Enable and start:

```bash
sudo systemctl enable kuiper-tts
sudo systemctl start kuiper-tts
```

### Option 4: Using Docker

Create `Dockerfile`:

```dockerfile
FROM python:3.11-slim

WORKDIR /app

# Install system dependencies
RUN apt-get update && apt-get install -y \
    build-essential \
    && rm -rf /var/lib/apt/lists/*

# Install Python dependencies
COPY backend/requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy application
COPY . .

# Set environment
ENV KUIPER_ENV=production

# Expose port
EXPOSE 8765

# Run server
CMD ["python", "run_server.py"]
```

Build and run:

```bash
docker build -t kuiper-tts .
docker run -d \
  -p 8765:8765 \
  -v $(pwd)/recordings:/app/recordings \
  -v $(pwd)/data:/app/data \
  -v $(pwd)/.env:/app/.env \
  kuiper-tts
```

## Reverse Proxy (Nginx)

Example Nginx configuration:

```nginx
server {
    listen 80;
    server_name yourdomain.com;

    location / {
        proxy_pass http://127.0.0.1:8765;
        proxy_http_version 1.1;
        proxy_set_header Upgrade $http_upgrade;
        proxy_set_header Connection 'upgrade';
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
        proxy_cache_bypass $http_upgrade;
        
        # Increase timeouts for long-running requests
        proxy_read_timeout 300s;
        proxy_connect_timeout 75s;
    }
}
```

## Monitoring

### Health Check

The application provides a health check endpoint:

```bash
curl http://localhost:8765/api/health
```

Response includes:
- `status`: "healthy" or "degraded"
- `version`: Application version
- `environment`: Current environment
- `training_active`: Whether training is in progress
- `system_analyzed`: Whether system analysis completed

### Logging

Logs are written to:
- Console (stdout/stderr)
- File (if `KUIPER_LOG_FILE` is set)

Log levels:
- `DEBUG`: Detailed debugging information
- `INFO`: General informational messages
- `WARNING`: Warning messages
- `ERROR`: Error messages

### Metrics to Monitor

- API response times
- Error rates (4xx, 5xx)
- Training job status
- Disk space usage (recordings, data, logs)
- Memory usage
- CPU usage

## Security Best Practices

1. **Never expose the API directly to the internet**
   - Use a reverse proxy (Nginx, Apache)
   - Implement SSL/TLS (HTTPS)

2. **Restrict CORS origins**
   - Only allow your frontend domain(s)
   - Never use `*` in production

3. **File Upload Security**
   - Validate file types
   - Limit file sizes
   - Scan for malware (if handling untrusted uploads)

4. **Rate Limiting**
   - Enable rate limiting in production
   - Adjust limits based on your use case

5. **Path Traversal Protection**
   - All file operations validate paths
   - User input is sanitized

6. **Error Messages**
   - Don't expose internal errors to users
   - Log detailed errors server-side

## Troubleshooting

### Server Won't Start

1. Check Python version (requires 3.10+)
2. Verify all dependencies are installed
3. Check port availability
4. Review logs for errors

### Training Fails

1. Verify GPU drivers (if using GPU)
2. Check available disk space
3. Review training logs
4. Ensure recordings are valid

### API Errors

1. Check CORS configuration
2. Verify rate limiting settings
3. Review request/response logs
4. Check file permissions

## Backup and Recovery

### Important Data to Backup

- `recordings/` - User recordings
- `data/` - Training data and models
- `.env` - Configuration (keep secure)

### Backup Script Example

```bash
#!/bin/bash
BACKUP_DIR="/backups/kuiper-tts"
DATE=$(date +%Y%m%d_%H%M%S)

mkdir -p "$BACKUP_DIR"

# Backup recordings
tar -czf "$BACKUP_DIR/recordings_$DATE.tar.gz" recordings/

# Backup data
tar -czf "$BACKUP_DIR/data_$DATE.tar.gz" data/

# Backup configuration
cp .env "$BACKUP_DIR/env_$DATE"
```

## Performance Tuning

### Uvicorn Workers

For production, use multiple workers:

```bash
uvicorn backend.api.main:app \
  --workers 4 \
  --host 127.0.0.1 \
  --port 8765
```

### Resource Limits

- **Memory**: Ensure sufficient RAM for training
- **Disk**: Monitor disk space for recordings and models
- **CPU/GPU**: Allocate resources based on training needs

## Updates and Maintenance

1. **Update Dependencies**
   ```bash
   pip install -r backend/requirements.txt --upgrade
   cd app && npm update
   ```

2. **Database Migrations** (if applicable)
   - Review changelog
   - Test in staging first

3. **Restart Services**
   ```bash
   sudo systemctl restart kuiper-tts
   ```

## Support

For issues or questions:
- Check logs: `tail -f logs/kuiper.log`
- Review health endpoint: `/api/health`
- Check system resources: `htop`, `df -h`
