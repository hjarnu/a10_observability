# Monitoring Stack with Prometheus, Grafana, and Renderer

This repository contains a setup for a monitoring of A10 Networks devices using Docker containers. The stack includes:

1. **Prometheus**: For scraping and storing metrics.
2. **Grafana**: For visualizing and alerting based on metrics.
3. **Grafana Image Renderer**: For rendering graphs as images, for alerts.
4. **Prometheus exporters**: For scraping metrics from ACOS devices below version 5.2.0. The full code is located here: https://github.com/a10networks/PrometheusExporter/blob/master/acos_exporter.py

Additionally, there is a Python script included for automating the update of Prometheus configuration by fetching zone details from an A10 API.

## Prerequisites

- Docker and Docker Compose installed on your system.
- SSL certificates for Grafana (located at `./prod_stac/certs/`).
- Python 3.x installed along with `requests` and `PyYAML` libraries.

## Getting Started

1. **Clone the Repository:**

   ```bash
   git clone https://github.com/hjarnu/a10_observability
   chown -R 65534:65534 /opt/monitoring/prod_stack/prometheus_data
   chown -R 472:472 /opt/monitoring/prod_stack/grafana_data
   chown -R 472:472 /opt/monitoring/prod_stack/certs/grafana.crt
   chown -R 472:472 /opt/monitoring/prod_stack/certs/grafana.key
   ```

2. **Build a Docker image for Prometheus Exporter:**

   ```bash
   docker build -t test-prometheus-exporter .
   ```

3. **Generate certificates for Grafana, or import your own**

   Generate the certificates and place them in the certs folder:

   ```bash
   openssl genrsa -out ./certs/grafana.key 2048
   openssl req -new -key ./certs/grafana.key -out ./certs/grafana.csr
   openssl x509 -req -days 365 -in ./certs/grafana.csr -signkey ./certs/grafana.key -out ./certs/grafana.crt
   chmod 400 ./certs/grafana.key ./certs/grafana.crt
   ```

   Make sure your SSL certificate and key (.crt and .key) are placed in `./prod_stack/certs/`.

4. **Configure Prometheus:**

   Specify your IP addresses and job names in the`prometheus.yml` configuration file in the `./configuration/prometheus/` directory. The Python script included in this repository will update this configuration file with endpoints fetched from the A10 API.

5. **Run the Stack:**

   Run the following command to start all services:

   ```bash
   docker-compose up -d
   ```

   This command will pull the required Docker images and start the Prometheus, Grafana, and Renderer services.

6. **Access the Services:**

   - **Prometheus**: `http://localhost:9090`
   - **Grafana**: `https://localhost:3000` (Grafana is configured to use HTTPS)
   - **Grafana Image Renderer**: The renderer will run on `http://localhost:8081`

## Python Script for Automated Configuration

The Python script `update_prometheus_config.py` is used to dynamically update Prometheus configuration by fetching zone details from an A10 Networks API. It does the following:

- Authenticates with the A10 API using provided credentials.
- Retrieves a list of zones and updates the Prometheus `prometheus.yml` configuration file.
- Reloads the Prometheus service to apply the new configuration.

### Running the Script

To run the script, ensure Python 3.x is installed and the required libraries (`requests` and `PyYAML`) are available. You can install the dependencies using:

```bash
pip install requests PyYAML
```

Run the script using:

```bash
python update_prometheus_config.py
```

Ensure that you replace the hardcoded credentials in the script with your actual credentials.

## Configuration Details

### Prometheus

Prometheus is configured with the following parameters:

- **Retention Time**: Data is retained for 30 days (`--storage.tsdb.retention.time=30d`).
- **Admin API Enabled**: The admin API is enabled (`--web.enable-admin-api`), allowing for dynamic reloading.

### Grafana

Grafana is configured to:

- Use HTTPS with provided certificates.
- Include additional environment variables for rendering and logging.

### Grafana Image Renderer

The Grafana Image Renderer is configured to:

- Ignore HTTPS errors (`IGNORE_HTTPS_ERRORS=true`).

## Resource Limits

The `docker-compose.yml` file defines resource limits for each service to ensure stable operation:

- **Prometheus**: Limited to 2 CPU and 1GB of memory.
- **Grafana**: Limited to 1 CPU and 400MB of memory.
- **Renderer**: Limited to 0.5 CPU and 200MB of memory.
- **Exporters**: Limited to 0.5 CPU and 200MB of memory

## License

This project is licensed under the MIT License.

## Support

If you encounter any issues or have questions, feel free to open an issue in the repository.

---

