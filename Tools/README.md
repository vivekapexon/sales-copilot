# Redshift Query Executor Tool

## Overview

The `redshift_query_executor.py` is a Python-based AWS Lambda function that provides a secure and efficient way to execute SQL queries against Amazon Redshift data warehouses. This tool leverages the Redshift Data API to perform database operations without requiring direct database connections or managing connection pools.

## Key Features

- **Serverless Execution**: Runs as an AWS Lambda function for automatic scaling and cost optimization
- **Secure Authentication**: Uses AWS Secrets Manager for database credentials
- **Parameter Store Integration**: Retrieves configuration from AWS Systems Manager Parameter Store
- **Asynchronous Query Execution**: Supports long-running queries with status polling
- **Flexible Result Handling**: Returns query results in JSON format with proper data type conversion
- **Error Handling**: Comprehensive error handling with detailed error messages
- **Timeout Management**: Configurable polling intervals and maximum execution times

## Prerequisites

### AWS Services Required
- **Amazon Redshift**: Data warehouse cluster or serverless workgroup
- **AWS Systems Manager Parameter Store**: For storing configuration parameters
- **AWS Secrets Manager**: For storing database credentials
- **AWS Lambda**: For executing the function
- **IAM Permissions**: Appropriate permissions for accessing Redshift, SSM, and Secrets Manager

### IAM Permissions
The Lambda function execution role must have the following permissions:

```json
{
    "Version": "2012-10-17",
    "Statement": [
        {
            "Effect": "Allow",
            "Action": [
                "redshift-data:ExecuteStatement",
                "redshift-data:DescribeStatement",
                "redshift-data:GetStatementResult"
            ],
            "Resource": "*"
        },
        {
            "Effect": "Allow",
            "Action": [
                "ssm:GetParameter"
            ],
            "Resource": "arn:aws:ssm:*:*:parameter/REDSHIFT_WORKGROUP"
        },
        {
            "Effect": "Allow",
            "Action": [
                "ssm:GetParameter"
            ],
            "Resource": "arn:aws:ssm:*:*:parameter/SC_REDSHIFT_DATABASE"
        },
        {
            "Effect": "Allow",
            "Action": [
                "ssm:GetParameter"
            ],
            "Resource": "arn:aws:ssm:*:*:parameter/SC_REDSHIFT_SECRET_ARN"
        },
        {
            "Effect": "Allow",
            "Action": [
                "secretsmanager:GetSecretValue"
            ],
            "Resource": "*"
        }
    ]
}
```

## Configuration

### Parameter Store Parameters

Create the following parameters in AWS Systems Manager Parameter Store:

1. **`REDSHIFT_WORKGROUP`** (String)
   - Description: Name of the Redshift workgroup
   - Example: `my-redshift-workgroup`

2. **`SC_REDSHIFT_DATABASE`** (String)
   - Description: Name of the Redshift database
   - Example: `sales_copilot_db`

3. **`SC_REDSHIFT_SECRET_ARN`** (String)
   - Description: ARN of the secret containing Redshift credentials
   - Example: `arn:aws:secretsmanager:us-east-1:123456789012:secret:redshift-credentials-AbCdEf`

### Secrets Manager Secret

Create a secret in AWS Secrets Manager with the following structure:

```json
{
    "username": "your_redshift_username",
    "password": "your_redshift_password"
}
```

## API Reference

### Lambda Function Input

The function expects an event payload with the following structure:

```json
{
    "sql_query": "SELECT * FROM your_table LIMIT 10",
    "return_results": true
}
```

#### Parameters

- **`sql_query`** (string, required): The SQL query to execute
- **`return_results`** (boolean, optional): Whether to return query results. Defaults to `true`

### Lambda Function Output

#### Success Response (200)

```json
{
    "statusCode": 200,
    "body": {
        "status": "finished",
        "rows": [
            {
                "column1": "value1",
                "column2": 123,
                "column3": true
            }
        ],
        "statement_id": "statement-uuid"
    }
}
```

#### Success Response (No Results) (200)

```json
{
    "statusCode": 200,
    "body": {
        "status": "finished",
        "statement_id": "statement-uuid"
    }
}
```

#### Error Response (400/500)

```json
{
    "statusCode": 400,
    "body": {
        "error": "Missing 'sql_query' in request"
    }
}
```

```json
{
    "statusCode": 500,
    "body": {
        "status": "error",
        "message": "execute_statement error: detailed error message"
    }
}
```

## Usage Examples

### Basic SELECT Query

```json
{
    "sql_query": "SELECT customer_id, customer_name FROM customers WHERE status = 'active' LIMIT 100"
}
```

### Data Manipulation Query

```json
{
    "sql_query": "INSERT INTO sales_log (customer_id, product_id, sale_date) VALUES (123, 456, CURRENT_DATE)",
    "return_results": false
}
```

### Complex Analytics Query

```json
{
    "sql_query": "SELECT region, SUM(sales_amount) as total_sales, COUNT(*) as transaction_count FROM sales_data WHERE sale_date >= '2024-01-01' GROUP BY region ORDER BY total_sales DESC"
}
```

## Configuration Constants

The following constants can be modified in the code:

- **`DEFAULT_SQL_LIMIT`**: Default maximum rows to return (default: 1000)
- **`SQL_POLL_INTERVAL_SECONDS`**: Polling interval for query status (default: 0.5 seconds)
- **`SQL_POLL_MAX_SECONDS`**: Maximum wait time for query completion (default: 30.0 seconds)

## Data Type Mapping

The tool automatically converts Redshift data types to appropriate Python/JSON types:

| Redshift Type | Python Type |
|---------------|-------------|
| VARCHAR, CHAR | string |
| INTEGER, BIGINT | number (longValue) |
| DECIMAL, FLOAT | number (doubleValue) |
| BOOLEAN | boolean |
| DATE, TIMESTAMP | string |
| BLOB | string (base64) |
| NULL | null |

## Error Handling

The function handles various error scenarios:

- **Missing SQL Query**: Returns 400 with error message
- **Parameter Store Errors**: Logs error and returns None (function continues with None values)
- **Redshift Connection Errors**: Returns 500 with detailed error message
- **Query Execution Failures**: Returns 500 with status and error details
- **Timeout Errors**: Returns 500 when query doesn't complete within `SQL_POLL_MAX_SECONDS`

## Deployment

### AWS Lambda Deployment

1. **Package the Function**:
   ```bash
   zip redshift_query_executor.zip redshift_query_executor.py
   ```

2. **Create Lambda Function**:
   ```bash
   aws lambda create-function \
     --function-name redshift-query-executor \
     --runtime python3.9 \
     --role arn:aws:iam::account-id:role/lambda-redshift-role \
     --handler redshift_query_executor.lambda_handler \
     --zip-file fileb://redshift_query_executor.zip \
     --timeout 300 \
     --memory-size 256
   ```

3. **Environment Variables** (Optional):
   - Set `DEFAULT_SQL_LIMIT`, `SQL_POLL_INTERVAL_SECONDS`, `SQL_POLL_MAX_SECONDS` as needed

### Testing

Test the function using AWS Lambda console or CLI:

```bash
aws lambda invoke \
  --function-name redshift-query-executor \
  --payload '{"sql_query": "SELECT 1 as test_column", "return_results": true}' \
  output.json
```

## Monitoring and Logging

- **CloudWatch Logs**: All print statements and errors are logged to CloudWatch
- **CloudWatch Metrics**: Lambda execution metrics are automatically captured
- **X-Ray**: Enable X-Ray tracing for performance monitoring

## Security Considerations

- **Least Privilege**: IAM role should have minimal required permissions
- **Encryption**: Use encrypted parameters in Parameter Store
- **Network Security**: Ensure Redshift cluster is in private subnets
- **Audit Logging**: Enable CloudTrail for API call auditing

## Performance Optimization

- **Query Optimization**: Ensure SQL queries are optimized with appropriate indexes
- **Result Limiting**: Use LIMIT clauses to prevent large result sets
- **Timeout Tuning**: Adjust `SQL_POLL_MAX_SECONDS` based on typical query durations
- **Memory Allocation**: Increase Lambda memory for complex queries

## Troubleshooting

### Common Issues

1. **Parameter Not Found**: Verify parameter names and paths in Parameter Store
2. **Access Denied**: Check IAM permissions and resource policies
3. **Query Timeout**: Increase `SQL_POLL_MAX_SECONDS` or optimize query
4. **Connection Errors**: Verify Redshift workgroup and database names

### Debug Steps

1. Check CloudWatch logs for detailed error messages
2. Verify parameter values in Parameter Store
3. Test Redshift connectivity using AWS Console
4. Validate SQL syntax and permissions

## Support

For issues or questions:
- Check AWS documentation for Redshift Data API
- Review CloudWatch logs for error details
- Verify IAM permissions and resource configurations