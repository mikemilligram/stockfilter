# Use an official Python runtime as a parent image
FROM python:3.11-slim

# Set working directory
WORKDIR /app

# Copy requirements file
COPY requirements.txt .

# Install dependencies
RUN pip install --no-cache-dir -r requirements.txt

# Install curl (required for Tailwind CLI install)
RUN apt-get update && apt-get install -y curl && rm -rf /var/lib/apt/lists/*

# Install Tailwind CSS CLI (standalone, no npm needed)
RUN curl -sSL -o /usr/local/bin/tailwindcss "https://github.com/tailwindlabs/tailwindcss/releases/latest/download/tailwindcss-linux-x64" \
    && chmod +x /usr/local/bin/tailwindcss

# Copy the rest of the application
COPY . .

# Build Tailwind CSS after all files are in place
RUN mkdir -p static/dist \
    && tailwindcss -i ./static/src/input.css -o ./static/dist/tailwind.css --minify

# Expose port
EXPOSE 5000

# Set environment variables
ENV FLASK_APP=app.py

# Run the application with hot reload
CMD ["flask", "run", "--host=0.0.0.0"]
