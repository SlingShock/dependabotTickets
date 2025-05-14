Try AI directly in your favorite apps … Use Gemini to generate drafts and refine content, plus get Gemini Advanced with access to Google’s next-gen AI for $19.99 $0 for 1 month
dependabotTickets.py
import json
import base64
import requests
import boto3
import os
from datetime import datetime, timedelta

DRY_RUN = os.environ.get("DRY_RUN", "false").lower() == "true"

client = boto3.client('sns')
SNS_TOPIC_ARN = os.environ["SNS_TOPIC_ARN"]

# GitHub configuration
ORGANIZATION_NAME = os.environ["ORGANIZATION_NAME"]
PERSONAL_ACCESS_TOKEN = os.environ["GITHUB_ACCESS_TOKEN"]
GH_HEADERS = {
    "Accept": 'application/vnd.github+json',
    "Authorization": f"Bearer {PERSONAL_ACCESS_TOKEN}"
}

# Jira configuration
KEY = os.environ["JIRA_PROJECT_KEY"]
SECURITY_EPIC = os.environ["JIRA_SECURITY_EPIC"]
JIRA_BASE_URL = os.environ["JIRA_BASE_URL"]
JIRA_URL = f"{JIRA_BASE_URL}/rest/api/3"
USERNAME = os.environ["JIRA_USERNAME"]
API_TOKEN = os.environ["JIRA_API_TOKEN"]

# Updated headers and auth setup
JIRA_HEADERS = {
    "Accept": "application/json",
    "Content-Type": "application/json"
}

def get_next_link(response_headers):
    links = response_headers.get('Link', '')
    next_link = [link for link in links.split(',') if 'rel="next"' in link]
    if next_link:
        url = next_link[0].split(';')[0].strip()
        return url.strip('<>')
    return None

def get_dependabot_alerts(repo_name):
    dependabot_alerts_url = f"https://api.github.com/repos/{ORGANIZATION_NAME}/{repo_name}/dependabot/alerts?state=open"
    dep_list = []

    while dependabot_alerts_url:
        response = requests.get(dependabot_alerts_url, headers=GH_HEADERS)
        if response.status_code != 200:
            return []
        dep_list.extend(response.json())
        dependabot_alerts_url = get_next_link(response.headers)

    return dep_list

def get_highest_severity(alerts):
    severity_levels = ["none", "low", "medium", "high", "critical"]
    highest_severity = "none"

    for alert in alerts:
        severity = alert['security_advisory']['severity']
        if severity_levels.index(severity) > severity_levels.index(highest_severity):
            highest_severity = severity
        if highest_severity == "critical":
            break

    return highest_severity

def make_jira_request(method, endpoint, data=None):
    """
    Helper function to make authenticated Jira API requests
    """
    url = f"{JIRA_URL}/{endpoint}"
    
    try:
        response = requests.request(
            method,
            url,
            headers=JIRA_HEADERS,
            auth=(USERNAME, API_TOKEN),
            json=data if data else None
        )
        return response
    except Exception as e:
        print(f"Error making Jira request: {e}")
        raise

def check_for_ticket(project_key, security_epic, label):
    """Check for existing ticket with given criteria"""

    jql = f"project = {project_key} AND 'Epic Link' = '{security_epic}' AND (labels = '{label}' AND labels = 'dependencies') AND status IN ('Open', 'To Do', 'In Progress')"
    
    print(f"\nChecking for existing ticket:")
    print(f"JQL Query: {jql}")
    
    response = make_jira_request('GET', f'search?jql={jql}')
    
    if response.status_code != 200:
        print(f"Error searching for tickets: {response.text}")
        return "Continue"
    
    result = response.json()
    issue_count = len(result.get('issues', []))
    print(f"Found {issue_count} matching issues")
    
    return "Canceled" if issue_count > 0 else "Continue"

def get_field_values():
    """Fetch available values for custom fields"""
    
    # First, get all fields to see the field details
    response = make_jira_request('GET', 'field')
    
    if response.status_code != 200:
        print(f"Error getting fields: {response.text}")
        return None
        
    fields = response.json()
    
    # Find the field we're interested in
    client_program_field = next((field for field in fields if field['id'] == 'customfield_11536'), None)
    
    if client_program_field:
        print(f"\nField Details for customfield_11536:")
        print(json.dumps(client_program_field, indent=2))
        
        # If it's a custom field with options, get the options
        if 'schema' in client_program_field and client_program_field['schema'].get('type') in ['option', 'array']:
            context_id = client_program_field.get('context')
            if context_id:
                options_response = make_jira_request('GET', f'field/{client_program_field["id"]}/context/{context_id}/option')
                if options_response.status_code == 200:
                    print("\nAvailable options:")
                    print(json.dumps(options_response.json(), indent=2))
                else:
                    print(f"Error getting options: {options_response.text}")
    else:
        print("Field customfield_11536 not found")
    
    return client_program_field

def get_cascading_field_options():
    """Fetch available options for the cascading select field"""
    
    # Create a test or dummy issue to get the field configuration
    meta_response = make_jira_request('GET', f'issue/createmeta?projectKeys={KEY}&issuetypeNames=Task&expand=projects.issuetypes.fields')
    
    if meta_response.status_code != 200:
        print(f"Error getting metadata: {meta_response.text}")
        return None
        
    metadata = meta_response.json()
    
    try:
        # Navigate through the metadata to find our field
        projects = metadata.get('projects', [])
        if projects:
            issue_types = projects[0].get('issuetypes', [])
            if issue_types:
                fields = issue_types[0].get('fields', {})
                client_program_field = fields.get('customfield_11536', {})
                
                if client_program_field:
                    print("\nField Configuration:")
                    print(json.dumps(client_program_field, indent=2))
                    
                    # Get the allowedValues if they exist
                    allowed_values = client_program_field.get('allowedValues', [])
                    if allowed_values:
                        print("\nAllowed Values:")
                        print(json.dumps(allowed_values, indent=2))
                        return allowed_values
                    
    except Exception as e:
        print(f"Error parsing metadata: {str(e)}")
    
    return None

def make_jira_ticket(repo_summary, dependabot_url, priority_number, ticket_due_date):
    """Create a new Jira ticket"""
    
    label = repo_summary
    ticket_check = check_for_ticket(KEY, SECURITY_EPIC, label)

    if ticket_check == "Continue":
        # Description in Atlassian Document Format (ADF)
        description = {
            "version": 1,
            "type": "doc",
            "content": [
                {
                    "type": "paragraph",
                    "content": [
                        {
                            "type": "text",
                            "text": "Update dependencies to remove security vulnerabilities displayed in "
                        },
                        {
                            "type": "text",
                            "text": dependabot_url,
                            "marks": [
                                {
                                    "type": "link",
                                    "attrs": {
                                        "href": dependabot_url
                                    }
                                }
                            ]
                        }
                    ]
                }
            ]
        }

        body = {
            "fields": {
                "project": {"key": JIRA_PROJECT_KEY},
                "summary": f"Security updates for {repo_summary}",
                "description": description,
                "duedate": ticket_due_date,
                "issuetype": {"name": "Task"},
                "priority": {"id": priority_number},
                "labels": [label, "dependencies"],
                "customfield_10007": SECURITY_EPIC,
                "customfield_10300": {"value": "No"},
                "customfield_10301": {"value": "All"},
                "customfield_11428": [{"value": 'No'}],
                "customfield_11434": {"value": "Product Support/Maintenance"},
                "customfield_11435": {"value": "RewardStation"},
                "customfield_11536": {
                    "id": "11881",  # All Clients
                    "child": {
                        "id": "11882"  # Platform Enhancements and Maintenance
                    }
                }
            }
        }

        if DRY_RUN:
            print(f"DRY RUN: Would create ticket for {repo_summary}")
            return {"message": "Dry run - ticket not created"}
        else:
            response = make_jira_request('POST', 'issue', data=body)
            if response.status_code in [200, 201]:
                return response.json()
            else:
                print(f"Error creating ticket: {response.text}")
                return None
    else:
        return f"Ticket already exists for {repo_summary}"
    
def get_custom_properties(repo_name):
    property_url = f"https://api.github.com/repos/{ORGANIZATION_NAME}/{repo_name}/properties/values"
    response = requests.get(property_url, headers=GH_HEADERS)
    if response.status_code == 200:
        return response.json()
    return []

def send_error_email(subject, message):
    """Send an error notification email via Amazon SNS."""
    try:
        response = sns_client.publish(
            TopicArn=SNS_TOPIC_ARN,
            Subject=subject,
            Message=message
        )
        return response
    except Exception as e:
        print(f"Failed to send error email: {e}")
        return None

def lambda_handler(event, context):
    try:
        # Add this at the beginning of your processing
        #print("Fetching cascading field options...")
        #cascading_options = get_cascading_field_options()
        #print(f"Cascading options: {json.dumps(cascading_options, indent=2) if cascading_options else 'Not found'}")
        #return
    
        repo_list = []
        api_url = f"https://api.github.com/orgs/{ORGANIZATION_NAME}/repos?type=private&per_page=100&page=1"

        while api_url:
            response = requests.get(api_url, headers=GH_HEADERS)
            if response.status_code != 200:
                break
            repo_list.extend(response.json())
            api_url = get_next_link(response.headers)

        repository_info_list = []
  
        for item in repo_list:
            repo = item['name']
            
            # Fetch and filter custom properties
            custom_properties = get_custom_properties(repo)
            property_filter = next((prop for prop in custom_properties if prop['property_name'] == "dependencies"), None)
            if property_filter['value'] == 'false':
                continue
            
            dalerts = get_dependabot_alerts(repo)

            if not dalerts:
                repo_info = {
                    "Repository Name": repo,
                    "URL": item['html_url'],
                    "Dependabot Alert Count": len(dalerts)
                }
            else:
                severity = get_highest_severity(dalerts)
                severity_number = '0'
                due_date = None
                if severity == 'critical':
                    severity_number = '2'
                    due_date = (datetime.utcnow() + timedelta(days=5)).strftime("%Y-%m-%d")
                elif severity == 'high':
                    severity_number = '3'
                    due_date = (datetime.utcnow() + timedelta(days=14)).strftime("%Y-%m-%d")
                elif severity == 'medium':
                    severity_number = '4'
                    due_date = (datetime.utcnow() + timedelta(days=30)).strftime("%Y-%m-%d")
                elif severity == 'low':
                    severity_number = '5'

                make_jira_ticket(repo, f"{item['html_url']}/security", severity_number, due_date)

            repo_info = {
                "Repository Name": repo,
                "URL": item['html_url'],
                "Dependabot Alert Count": len(dalerts)
            }

            repository_info_list.append(repo_info)

        return {
            "statusCode": 200,
            "body": json.dumps(repository_info_list)
        }

    except Exception as e:
        error_message = f"An error occurred: {str(e)}"
        send_error_email(subject="Lambda Function Error", message=error_message)
        return {
            "statusCode": 500,
            "body": json.dumps({"error": error_message})
        }

if __name__ == "__main__":
    # Simulate an EventBridge event
    test_event = {
        "version": "0",
        "id": "test-event",
        "detail-type": "Scheduled Event",
        "source": "aws.events",
        "account": "123456789012",
        "time": "2024-02-11T12:00:00Z",
        "region": "us-east-1",
        "detail": {}
    }
    lambda_handler(test_event, None)
