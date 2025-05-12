FROM python:3.11.10-bullseye

# Install system dependencies and wkhtmltopdf in one layer to reduce image size
RUN apt-get update && apt-get install -y \
    wget \
    xz-utils \
    libxrender1 \
    libjpeg62-turbo \
    fontconfig \
    xfonts-base \
    xfonts-75dpi \
    && wget https://github.com/wkhtmltopdf/packaging/releases/download/0.12.6.1-2/wkhtmltox_0.12.6.1-2.bullseye_amd64.deb \
    && dpkg -i wkhtmltox_0.12.6.1-2.bullseye_amd64.deb \
    && rm wkhtmltox_0.12.6.1-2.bullseye_amd64.deb \
    && rm -rf /var/lib/apt/lists/* \
    && apt-get clean

# Install pipenv
RUN pip install pipenv