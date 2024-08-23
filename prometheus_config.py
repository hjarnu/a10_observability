import requests
import json
import os
import yaml

#Prompt for credentials
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
output_file = ""
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

        api_endpoint_value = [f"/ddos/dst/zone/{zone}/stats" for zone in zones]

        prometheus_config = {
            'scrape_configs': [
                {   'job_name': 'a10-tps-device-1',
                    'scheme': 'http',
                    'metrics_path': '/metrics',
                    'scrape_interval': '15s',
                    'static_configs': [
                        {
                            'targets': ['exporter:port']
                        }
                    ],
                    'params': {
                                'host_ip': ["a10"],
                                'api_endpoint': api_endpoint_value
                    }
                },
                {
                    'job_name': 'a10-tps-device-2',
                    'scheme': 'http',
                    'metrics_path': '/metrics',
                    'scrape_interval': '15s',
                    'static_configs': [
                        {
                            'targets': ['exporter:port']
                        }
                    ],
                    'params': {
                                'host_ip': ["a10"],
                                'api_endpoint': [f"/ddos/dst/zone/{zone}/stats" for zone in zones]
                    }
                },
                {
                    'job_name': 'a10-tps-akto-mitigator',
                    'scheme': 'http',
                    'metrics_path': '/metrics',
                    'scrape_interval': '15s',
                    'static_configs': [
                        {
                            'targets': ['exporter:port']
                        }
                    ],
                    'params': {
                                'host_ip': ["a10"],
                                'api_endpoint': [f"/ddos/dst/zone/{zone}/stats" for zone in zones]
                    }
                }
            ]
        }
        
        # Write the configuration to the Prometheus file
        with open(prometheus_config_file, 'w') as file:
            yaml.dump(prometheus_config, file, default_flow_style=False)
        
        # Reload Prometheus to apply the new configuration
        os.system("curl -X POST http://localhost:9091-/reload")

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
