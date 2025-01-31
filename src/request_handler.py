import os
import json
import boto3
import logging
from datetime import datetime, timezone, timedelta
from typing import Dict, Any


logger = logging.getLogger()
logger.setLevel(logging.INFO)


def validate_request(topic_id: str, date_str: str) -> bool:
    """
    Validate request parameters.
    Only allows past dates (yesterday and before).
    """
    if not topic_id or not date_str:
        return False
    
    # Validate topic_id format (category#subcategory#post)
    if len(topic_id.split('#')) != 3:
        return False
    
    # Validate date format (YYYY-MM-DD)
    try:
        request_date = datetime.strptime(date_str, '%Y-%m-%d').date()
        today = datetime.now(timezone.utc).date()
        
        # Check if date is in the past
        if request_date >= today:
            return False
            
        return True
    except ValueError:
        return False


def lambda_handler(event: Dict[str, Any], context: Any) -> Dict[str, Any]:
    """Handle API Gateway requests to check or create summary requests."""
    logger.info("Processing request: %s", json.dumps(event))

    # Get and validate parameters
    params = event.get('queryStringParameters', {})
    topic_id = params.get('topic_id')
    date = params.get('date')

    if not validate_request(topic_id, date):
        return {
            'statusCode': 400,
            'body': json.dumps({
                'error': 'Invalid parameters. Expected: topic_id (cat#subcat#post) and date (YYYY-MM-DD) before today'
            })
        }

    try:
        dynamodb = boto3.resource('dynamodb')
        table = dynamodb.Table(os.environ['SUMMARIES_TABLE'])

        # Check if summary exists
        response = table.get_item(
            Key={'topic_id': topic_id, 'date': date}
        )

        if 'Item' in response:
            status = response['Item']['status']
            how_long_ago = datetime.now(timezone.utc) - datetime.fromisoformat(response['Item']['last_updated'])
            if how_long_ago <= timedelta(hours=1) or (status not in ['error', 'in_progress']):
                return {
                    'statusCode': 200,
                    'body': json.dumps(response['Item'])
                }

        # Create new summary request
        new_summary = {
            'topic_id': topic_id,
            'date': date,
            'status': 'in_progress',
            'created_at': datetime.now(timezone.utc).isoformat()
        }
        table.put_item(Item=new_summary)

        return {
            'statusCode': 202,
            'body': json.dumps(new_summary)
        }

    except Exception as e:
        logger.error("Error: %s", str(e), exc_info=True)
        return {
            'statusCode': 500,
            'body': json.dumps({'error': 'Internal server error'})
        }

    