"""
    This script pulls the zone list from the A10 TPS appliances and updates the Prometheus configuration to semi-automate the monitoring workflow.
    The setup includes two A10 TPS appliances, containing the same zone configuration.
    The script first attempts to connect to the first configured device; if successful, it establishes a connection to the API endpoint.
    If the primary device is unreachable, the script tries the secondary appliance.

    Once connected, the script authenticates using a username and password to retrieve an authentication token,
    then requests the zone-list data from the A10 TPS device.
    This response includes a 'zone-list' dictionary, where each entry represents an individual zone configuration.

    The important field is 'operational-mode'. This indicates the zone's current state, which may be:
        - 'monitor': Zone is under active DDoS protection;
        - 'learning': Zone is in learning mode, gathering traffic statistics, but not in the active protection mode;
        - 'idle': All activities are stopped.
    For monitoring, only zones in 'monitor' or 'learning' modes are relevant, as 'idle' zones do not collect traffic metrics.
    Including 'idle' zones in Prometheus and Grafana is redundant.
    The zones that were previously active but changed mode to 'idle' would remain the Prometheus data for the configured retention period.
    The script rewrites and saves  the endpoint section of the Prometheus configuration file, then reloads the configuration to apply changes.

"""

import requests
import json
import logging
import os
import yaml
import platform    # For getting the operating system name
import subprocess  # For executing a shell command
from datetime import datetime
import shutil  # For file backup

#IPs
detector_1 = "<ip1>"
detector_2 = "<ip2>"

# File to save the results
prometheus_config_file = "/opt/monitoring/prod_stack/configuration/prometheus/prometheus.yml"

logging.basicConfig(filename='/opt/monitoring/monitoring.log', level=logging.INFO,
                    format='%(asctime)s - %(levelname)s - %(message)s')

# Custom YAML dumper to prevent YAML anchors
class NoAliasDumper(yaml.SafeDumper):
    def ignore_aliases(self, data):
        return True


def backup_prometheus_config():
    """
    Create a backup of the Prometheus configuration file.
    """
    try:
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        backup_file = f"{prometheus_config_file}.bak_{timestamp}"
        shutil.copy(prometheus_config_file, backup_file)
        logging.info(f"Backup of Prometheus configuration created at {backup_file}")
    except Exception as e:
        logging.error(f"Failed to backup Prometheus configuration: {e}")


def ping(host):

    """
    Returns True if host (str) responds to a ping request.
    Remember that a host may not respond to a ping (ICMP) request even if the host name is valid.
    
    """
    try:
        # Option for the number of packets as a function of
        param = '-n' if platform.system().lower()=='windows' else '-c'

        # Building the command. Ex: "ping -c 1 google.com"
        command = ['ping', param, '1', host]

        return subprocess.call(command) == 0
        
    except Exception as e:
        logging.error(f"An error occurred while trying to ping hosts: {e}")
        return []


def authentication(host, username, password):
    """
    Returns signature token
    """
    auth_url = f"https://{host}/axapi/v3/auth"

    # Headers for the authentication request
    auth_headers = {
        "Content-Type": "application/json"
    }

    # Payload for the authentication request
    auth_payload = json.dumps({
        "credentials": {
            "username": username,
            "password": password
        }
    })

    try:
        response = requests.post(auth_url, headers=auth_headers, data=auth_payload, verify=False)
        response.raise_for_status()
        return response.json()["authresponse"]["signature"]
    
    except Exception as e:
        logging.error(f"Authentication failed for {host}: {e}")
        return None


def logoff(host, signature):
    """
    Log off from the API to end the session.
    """
    logoff_url = f"https://{host}/axapi/v3/logoff"
    headers = {"Authorization": f"A10 {signature}"}
    try:
        response = requests.post(logoff_url, headers=headers, verify=False)
        if response.status_code == 200:
            logging.info(f"Successfully logged off from {host}.")
        else:
            logging.error(f"Failed to log off from {host}: {response.status_code}")
    except Exception as e:
        logging.error(f"Error logging off from {host}: {e}")


def call_api(host, signature):
    """
    Make the API call to fetch zones
    """
    url = f"https://{host}/axapi/v3/ddos/dst/zone/"
    headers = {"Authorization": f"A10 {signature}", "Content-Type": "application/json"}
    
    try:
        response = requests.get(url, headers=headers, verify=False)
        if response.status_code == 200:
            data = response.json()
            zones = data.get('zone-list', [])
            idle_zones = [zone['zone-name'] for zone in zones if zone.get('operational-mode') == 'idle']
            if idle_zones:
                logging.info(f"Omitting Idle zones: {', '.join(idle_zones)}")
            api_endpoint_value = [f"/ddos/dst/zone/{zone['zone-name']}/stats" for zone in zones if zone['zone-name'] not in idle_zones]
            update_prometheus_config(api_endpoint_value)
        else:
            logging.error(f"Failed to retrieve zone data from {host}: {response.status_code}")
            logging.error(response.text)
    except Exception as e:
        logging.error(f"Error during API call to {host}: {e}")

def update_prometheus_config(api_endpoints):
    """
    Update Prometheus configuration file with new API endpoints.
    """
    backup_prometheus_config()  # Backup before modifying
    try:
        with open(prometheus_config_file, 'r') as file:
            prometheus_config = yaml.safe_load(file)
        
        for job in prometheus_config.get('scrape_configs', []):
            if job.get('job_name', '').startswith('a10-tps'):
                job['params']['api_endpoint'] = api_endpoints
        
        with open(prometheus_config_file, 'w') as file:
            yaml.dump(prometheus_config, file, default_flow_style=False, Dumper=NoAliasDumper)
        
        os.system("curl -X POST http://localhost:9090/-/reload")
        logging.info("Prometheus configuration updated and reloaded successfully.")
    except Exception as e:
        logging.error(f"Failed to update Prometheus configuration: {e}")


def main():
    """
    Main function to try connections with failover logic.
    """
    username = "<user>"
    password = "<password>"
    
    for detector in [detector_1, detector_2]:
        if ping(detector):
            logging.info(f"Detector {detector} is reachable. Attempting API connection...")
            signature = authentication(detector, username, password)
            if signature:
                call_api(detector, signature)
                logoff(detector, signature)
                return  # Exit after successful operation
            else:
                logging.warning(f"API connection to {detector} failed. Trying next detector...")
        else:
            logging.warning(f"Detector {detector} is unreachable by ping.")
    
    logging.error("Both detectors are unreachable or API connection failed. Unable to update configuration.")

if __name__ == "__main__":
    main()