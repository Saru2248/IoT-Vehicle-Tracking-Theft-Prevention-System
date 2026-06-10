# gunicorn.conf.py — loaded automatically by gunicorn when present in the CWD
# Run with:  gunicorn -c gunicorn.conf.py main:app
# Or Render Start Command:  gunicorn main:app   (config is auto-loaded)

workers  = 1          # Keep at 1: the VehicleSimulator is stateful in-memory
threads  = 4          # Handle concurrent requests within the single worker
timeout  = 120        # Give PDF generation enough time
loglevel = "info"
accesslog = "-"       # stdout — visible in Render logs
errorlog  = "-"       # stdout — visible in Render logs
