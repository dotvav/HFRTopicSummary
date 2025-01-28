import os
import json
import boto3
import logging
from typing import Dict, Any


logger = logging.getLogger()
logger.setLevel(logging.INFO)


def parse_dynamodb_image(image: Dict[str, Any]) -> Dict[str, Any]:
    """Extract values from DynamoDB Stream image format."""
    result = {}
    for key, value in image.items():
        result[key] = next(iter(value.values()))
    return result


def lambda_handler(event: Dict[str, Any], context: Any) -> None:
    """Process DynamoDB Stream events and send them to SQS."""
    logger.info("Processing Stream event: %s", json.dumps(event))
    
    sqs = boto3.client('sqs')
    queue_url = os.environ['QUEUE_URL']

    for record in event['Records']:
        if record['eventName'] != 'INSERT':
            continue

        try:
            new_image = parse_dynamodb_image(record['dynamodb']['NewImage'])
            
            message = {
                'topic_id': new_image['topic_id'],
                'date': new_image['date'],
                'status': new_image.get('status'),
                'created_at': new_image.get('created_at')
            }
            
            sqs.send_message(
                QueueUrl=queue_url,
                MessageBody=json.dumps(message)
            )
            logger.info("Message sent to SQS for topic: %s", message['topic_id'])

        except Exception as e:
            logger.error(
                "Error processing record: %s. Record: %s",
                str(e),
                json.dumps(record),
                exc_info=True
            )
