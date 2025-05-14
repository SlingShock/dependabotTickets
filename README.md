Try AI directly in your favorite apps … Use Gemini to generate drafts and refine content, plus get Gemini Advanced with access to Google’s next-gen AI for $19.99 $0 for 1 month
README.md
# Dependabot Tickets Lambda

This folder contains an AWS Lambda function written in Python that automates the process of monitoring GitHub repositories for open Dependabot security alerts and creating corresponding Jira tickets for remediation.

## What the Script Does
- **GitHub Integration:**
  - Connects to the GitHub API using a personal access token.
  - Iterates through all private repositories in a specified organization.
  - Retrieves open Dependabot alerts for each repository.
  - Checks custom repository properties to determine if dependency monitoring is enabled.

- **Severity Assessment:**
  - Determines the highest severity of open Dependabot alerts (low, medium, high, critical).
  - Assigns a Jira ticket priority and due date based on the severity.

- **Jira Integration:**
  - Checks if a Jira ticket already exists for the repository and alert type.
  - If not, creates a new Jira ticket in a specified project and epic, with appropriate fields, labels, and custom field values.
  - Uses Atlassian Document Format (ADF) for ticket descriptions.

- **Notifications:**
  - Sends error notifications via Amazon SNS if any issues occur during execution.

- **Dry Run Mode:**
  - Supports a DRY_RUN environment variable to simulate ticket creation without making changes.

## Usage
- Deploy this Lambda function in AWS.
- Set up a scheduled trigger (e.g., EventBridge) to run the function periodically.
- Configure the following environment variables:
  - `GITHUB_ACCESS_TOKEN`: GitHub personal access token
  - `ORGANIZATION_NAME`: GitHub organization name
  - `SNS_TOPIC_ARN`: SNS topic ARN for error notifications
  - `JIRA_BASE_URL`: Base URL for your Jira instance
  - `JIRA_USERNAME`: Jira username
  - `JIRA_API_TOKEN`: Jira API token
  - `DRY_RUN`: (optional) Set to `true` to enable dry run mode
  - `KEY`: Jira project key (default: `V8` in the script)
  - `SECURITY_EPIC`: Jira epic key for security tickets (default: `V8-13700` in the script)

These can be set as environment variables or modified directly in the script as needed.

## Requirements
- AWS Lambda execution role with permissions for SNS.
- Python 3.x runtime.
- The `boto3` and `requests` libraries (available in the AWS Lambda Python runtime by default).

## File
- `dependabotTickets.py`: The main Lambda handler script.
