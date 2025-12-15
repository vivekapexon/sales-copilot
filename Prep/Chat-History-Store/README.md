# Sales Copilot Chat Store

A Lambda function that provides REST API endpoints for managing chat sessions and messages, designed to integrate with a UI via API Gateway HTTP API v1.

## Prerequisites

### DynamoDB Tables

Create two DynamoDB tables with the following specifications:

#### 1. Chat Sessions Table
- **Partition Key**: `session_id` (String)
- **Global Secondary Index**: `user_id-index`
  - Partition Key: `user_id` (String)
  - Sort Key: `created_at` (String)

#### 2. Chat Messages Table  
- **Partition Key**: `session_id` (String)
- **Sort Key**: `message_timestamp` (Number)

### Parameter Store Variables

Set up the following SSM Parameter Store parameters:

- `SC_CHAT_SESSIONS_TABLE` - Name of the sessions DynamoDB table
- `SC_CHAT_MESSAGES_TABLE` - Name of the messages DynamoDB table

### IAM Permissions

The Lambda execution role needs permissions for:
- DynamoDB read/write access to both tables
- SSM GetParameter access
- CloudWatch Logs

## API Endpoints

| Method | Path | Description |
|--------|------|-------------|
| POST | `/sessions` | Create new chat session |
| GET | `/sessions` | List user sessions |
| GET | `/sessions/{id}` | Get session with messages |
| POST | `/sessions/{id}/messages` | Add message to session |


## Deployment

1. Create DynamoDB tables and SSM parameters
2. Deploy Lambda function with appropriate IAM role
3. Configure API Gateway HTTP API v1 to proxy requests to Lambda
4. Enable CORS if needed for web UI integration