FROM werkr-base:latest

WORKDIR /app

# Copy only Pipfile and Pipfile.lock first to leverage Docker cache
COPY Pipfile Pipfile.lock ./

# Create virtualenv in a specific location that we can volume mount
ENV PIPENV_VENV_IN_PROJECT=1
RUN pipenv sync

# Copy the application
COPY . .

EXPOSE 8000

# Command to run the Python script with more verbose logging
CMD ["pipenv", "run", "gunicorn", "-b", "0.0.0.0:80", "api.asgi:application", "-k", "uvicorn.workers.UvicornWorker", "--log-level", "debug"]