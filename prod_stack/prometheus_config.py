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

    """
    Makes an API call to the host. Uses authentication process with username and password to get the authentication token,
    which is used later for the call. The call is pulling the ddos destination zone information from the A10 TPS.
    The result is a 'zone-list' dictionary, which contains the list of dictionaries, each representing the individual zone configuration.
    Filters the zones with 'idle' operational-mode.
    Generates a new api_endpoint list, containing '/ddos/dst/zone/zone_name/stats' values for each active zone.
    Rewrites the api_endpoint section of the Prometheus config file.
    Reloads the Prometheus configuration to apply the changes.

    """
    # Prompt for credentials
    username = "<user>"
    password = "<password>"

    # URLs for authentication, API call, and logoff
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
                logging.info(f"Successful authentication: 200")

                # Parse the JSON response to get the list of zones
                data = response.json()
                zones = data.get('zone-list', [])

                # Filter zones where operational-mode is 'idle'
                idle_zones = [zone['zone-name'] for zone in zones if zone.get('operational-mode') == 'idle']
                
                # Log idle zones
                if idle_zones:
                    logging.info(f"Omiting Idle zones: {', '.join(idle_zones)}")
                else:
                    logging.info("No idle zones found.")

                # Generate the new API endpoint values excluding idle zones
                api_endpoint_value = [f"/ddos/dst/zone/{zone['zone-name']}/stats" 
                                      for zone in zones if zone['zone-name'] not in idle_zones]

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