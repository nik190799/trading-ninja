# api-service/Dockerfile (Stateless & Modified for Firebase Prompts)
# Use the official lightweight Python image.
FROM python:3.10-slim

# Set the working directory in the container.
WORKDIR /app

# Copy requirements from the api-service directory and install.
# The path is relative to the build context (the project root).
COPY api-service/requirements.txt .
# Eventlet is no longer needed. Gunicorn is still used as the process manager.
# --- MODIFICATION: Add firebase-admin dependency ---
RUN pip install --no-cache-dir -r requirements.txt firebase-admin
# --- END MODIFICATION ---


# This copies all .py files from the local api-service folder
# into the /app/ directory inside the container.
COPY api-service/*.py /app/

# The prompts are now fetched from Firestore, so the local directory is not copied.

# Copy the shared static folder from the root and the templates
# folder from within the api-service directory.
COPY static /app/static
# --- FIX: Corrected the typo from api--service to api-service ---
COPY api-service/templates /app/templates
# --- END FIX ---

# Set the port environment variable.
ENV PORT 8080

# --- FIX: Increase timeout to 300s (5 minutes) and adjust workers ---
# The mockup generation can be a long-running task. Increasing the timeout
# prevents the worker from being killed prematurely. Reducing workers to 1
# for this type of blocking task is more efficient.
CMD exec gunicorn --bind :$PORT --workers 1 --threads 4 --timeout 300 app:app
