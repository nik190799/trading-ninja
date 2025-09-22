# Use the official lightweight Python image.
# This Dockerfile MUST be in the root of your project (tradingNinja/Dockerfile).
FROM python:3.10-slim

# Set the working directory inside the container.
WORKDIR /app

# Copy the requirements file from the ninja-api-service directory.
# The path is relative to the build context (the tradingNinja folder).
COPY ninja-api-service/requirements.txt .

# Install the Python dependencies.
RUN pip install --no-cache-dir -r requirements.txt

# Copy the service account key into the container's working directory.
# This is the crucial step to fix the FileNotFoundError.
COPY serviceAccountKey.json .

# Copy the Python application source code.
COPY ninja-api-service/app.py .

# Copy the templates and static assets.
COPY ninja-api-service/templates ./templates
COPY static ./static

# Set the port environment variable that Cloud Run will use.
ENV PORT 8080

# Start the Gunicorn web server.
# This command runs your 'app' variable (the Flask app) from your 'app.py' file.
CMD exec gunicorn --bind :$PORT --workers 1 --threads 8 --timeout 0 app:app
