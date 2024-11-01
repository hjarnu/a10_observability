import requests
import json
import logging
import os
import yaml
import platform    # For getting the operating system name
import subprocess  # For executing a shell command

#IPs
detector_1 = "<ip1>"
detector_2 = "<ip2>"

# File to save the results
prometheus_config_file = "./configuration/prometheus/prometheus.yml"

logging.basicConfig(filename='/opt/monitoring/monitoring.log', level=logging.INFO,
                    format='%(asctime)s - %(levelname)s - %(message)s')

# Custom YAML dumper to prevent YAML anchors
class NoAliasDumper(yaml.SafeDumper):
    def ignore_aliases(self, data):
        return True


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
    

def call(host):
    # Prompt for credentials
    username = "<user>"
    password = "<password>"

    # URLs for authentication, zone details, and logoff
    auth_url = f"https://{host}/axapi/v3/auth"
    url = f"https://{host}/axapi/v3/ddos/dst/zone/"
    logoff_url = f"https://{host}/axapi/v3/logoff"
    
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

    # Authenticate to get the authorization signature
    try:
        auth_response = requests.post(auth_url, headers=auth_headers, data=auth_payload, verify=False)

        if auth_response.status_code == 200:
            auth_data = auth_response.json()
            signature = auth_data["authresponse"]["signature"]

            # Headers for the subsequent requests
            headers = {
                "Content-Type": "application/json",
                "Authorization": f"A10 {signature}"
            }

            # Make the API call:
            response = requests.get(url, headers=headers, verify=False)

            # Check if the request was successful
            if response.status_code == 200:
                logging.info(f"Successfull authentication: 200")

                # Parse the JSON response to get the list of zones
                data = response.json()
                zones = [zone['zone-name'] for zone in data.get('zone-list', [])]

                # Generate the new API endpoint values
                api_endpoint_value = [f"/ddos/dst/zone/{zone}/stats" for zone in zones]

                # Load the existing Prometheus configuration
                try:
                    with open(prometheus_config_file, 'r') as file:
                        prometheus_config = yaml.safe_load(file)

                    # Update the configuration
                    for job in prometheus_config.get('scrape_configs', []):
                        if job.get('job_name', '').startswith('a10-tps'):
                            job['params']['api_endpoint'] = api_endpoint_value

                    # Write the updated configuration to the file
                    with open(prometheus_config_file, 'w') as file:
                        yaml.dump(prometheus_config, file, default_flow_style=False,Dumper=NoAliasDumper)

                    # Reload Prometheus to apply the new configuration
                    os.system("curl -X POST http://localhost:9090/-/reload")

                    logging.info("Prometheus configuration updated and reloaded successfully.")
                
                except Exception as e:
                    logging.error(f"Unable to write changes to the Prometheus config file :{e}")

            else:
                logging.error(f"Failed to retrieve zone data: {response.status_code}")
                logging.error(response.text)

            # Log off to end the session
            logoff_response = requests.post(logoff_url, headers=headers, verify=False)
            if logoff_response.status_code == 200:
                logging.info("Successfully logged off.")
            else:
                logging.error(f"Failed to log off: {logoff_response.status_code}")

        else:
            logging.error(f"Failed to authenticate: {auth_response.status_code}")
            logging.error(auth_response.text)
        
    except Exception as e:
        logging.error(f"An error occurred while trying make the API call: {e}")
        return []

if ping(detector_1):
    logging.info(f"Detector {detector_1} is reachable. Trying to establish the API connection...")
    
    try:
        call(detector_1)
    except Exception as e:
        logging.error(f"An error occurred while trying to connect to the host {detector_1}: {e}")
    
elif ping(detector_2):
    logging.error(f"Detector {detector_1} is not reachable. Trying to ping {detector_2}...")
    logging.info(f"Detector {detector_2} is reachable. Trying to establish the API connection...")

    try:
        call(detector_2)
        
    except Exception as e:
        logging.error(f"An error occurred while trying to connect to the host {detector_2}: {e}")
else:
    logging.error(f"Both detectors {detector_1} and {detector_2} are not reachable. Unable to fetch the zone list!")