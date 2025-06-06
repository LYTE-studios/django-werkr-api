FROM werkr-base:latest

# Install redis-cli
RUN apt-get update && apt-get install -y redis-tools && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# Copy only Pipfile and Pipfile.lock first to leverage Docker cache
COPY Pipfile Pipfile.lock ./

# Create virtualenv in a specific location that we can volume mount
ENV PIPENV_VENV_IN_PROJECT=1
RUN pipenv sync

# Copy the application
COPY . .

EXPOSE 8000

# Command to run the Python script with more verbose logging and output capture
CMD ["pipenv", "run", "gunicorn", "-b", "0.0.0.0:80", "api.asgi:application", "-k", "uvicorn.workers.UvicornWorker", "--log-level", "debug", "--capture-output", "--preload"]