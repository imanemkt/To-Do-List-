# Use the official Python 3.13.0 image as the base image
FROM python:3.13.0-slim

# Set environment variables for Python
ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1

# Set the working directory inside the container
WORKDIR /app

# Install system dependencies (required for MySQL client and other libraries)
RUN apt-get update && apt-get install -y --no-install-recommends \
    default-libmysqlclient-dev \
    build-essential \
    && rm -rf /var/lib/apt/lists/*

# Copy the requirements file and install Python dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy the rest of the application code
COPY . .

# Expose port 8080 (Google Cloud Run requirement)
ENV PORT=8080
EXPOSE 8080

# Set environment variables for Cloud SQL
ENV MYSQL_USER="root"
ENV MYSQL_PASSWORD="gT@=MAmkB{PtX#7B"
ENV MYSQL_db="flask-mysql-instance"
ENV MYSQL_HOST="35.205.255.83"
ENV INSTANCE_CONNECTION_NAME="to-do-list-flask-449601:europe-west1:flask-mysql-instance"

# Command to run the application
CMD ["gunicorn", "--bind", "0.0.0.0:8080", "app:app"]