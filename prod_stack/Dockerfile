FROM ubuntu:latest

# Update package list and install required packages
RUN apt-get update --fix-missing && \
    apt-get install -y python3-pip python3 build-essential python3-venv && \
    rm -rf /var/lib/apt/lists/*

# Set up the application directory
COPY . /app
WORKDIR /app

# Create a virtual environment inside the container
RUN python3 -m venv venv

# Activate the virtual environment and install the requirements
RUN . venv/bin/activate && pip install --no-cache-dir -r requirements.txt

# Use the virtual environment's Python as the entry point
ENV PATH="/app/venv/bin:$PATH"

# Set entry point and command
ENTRYPOINT ["python3"]
CMD ["acos_exporter.py"]