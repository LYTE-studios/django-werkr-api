FROM python:3.11.10-bullseye

WORKDIR /app
COPY . .

RUN pip install pipenv 
RUN pipenv sync

# Install dependencies
RUN apt-get update && apt-get install -y \
    wget \
    xz-utils \
    libxrender1 \
    libjpeg62-turbo \
    fontconfig \
    xfonts-base \
    xfonts-75dpi \
    && rm -rf /var/lib/apt/lists/*

# Download and install wkhtmltopdf
RUN wget https://github.com/wkhtmltopdf/packaging/releases/download/0.12.6.1-2/wkhtmltox_0.12.6.1-2.bullseye_amd64.deb \
    && dpkg -i wkhtmltox_0.12.6.1-2.bullseye_amd64.deb \
    && rm wkhtmltox_0.12.6.1-2.bullseye_amd64.deb

EXPOSE 8000

# Command to run the Python script
CMD ["pipenv", "run", "gunicorn", "-b", "0.0.0.0:8000", "api.asgi:application", "-k", "uvicorn.workers.UvicornWorker"]