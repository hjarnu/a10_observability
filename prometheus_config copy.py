import requests
import json
import os
import yaml

# Custom YAML dumper to prevent YAML anchors
class NoAliasDumper(yaml.SafeDumper):
    def ignore_aliases(self, data):
        return True


# Prompt for credentials
username = "username"
password = "password"

# URLs for authentication, zone details, and logoff
auth_url = "https://a10/axapi/v3/auth"
url = "https://a10/axapi/v3/ddos/dst/zone/"
logoff_url = "https://a10/axapi/v3/logoff"

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

# File to save the results
prometheus_config_file = "./configuration/prometheus/prometheus.yml"

# Authenticate to get the authorization signature
auth_response = requests.post(auth_url, headers=auth_headers, data=auth_payload, verify=False)

if auth_response.status_code == 200:
    auth_data = auth_response.json()
    signature = auth_data["authresponse"]["signature"]
    
    # Headers for the subsequent requests
    headers = {
        "Content-Type": "application/json",
        "Authorization": f"A10 {signature}"
    }

    # Make the API call to fetch zone details
    response = requests.get(url, headers=headers, verify=False)

    # Check if the request was successful
    if response.status_code == 200:
        # Parse the JSON response to get the list of zones
        data = response.json()
        zones = [zone['zone-name'] for zone in data.get('zone-list', [])]

        # Generate the new API endpoint values
        api_endpoint_value = [f"/ddos/dst/zone/{zone}/stats" for zone in zones]

        # Load the existing Prometheus configuration
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
        os.system("curl -X POST http://localhost:9091/-/reload")

        print("Prometheus configuration updated and reloaded successfully.")
    else:
        print(f"Failed to retrieve zone data: {response.status_code}")
        print(response.text)

    # Log off to end the session
    logoff_response = requests.post(logoff_url, headers=headers, verify=False)
    if logoff_response.status_code == 200:
        print("Successfully logged off.")
    else:
        print(f"Failed to log off: {logoff_response.status_code}")
else:
    print(f"Failed to authenticate: {auth_response.status_code}")
    print(auth_response.text)
