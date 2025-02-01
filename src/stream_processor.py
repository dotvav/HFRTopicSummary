import os
import json
import boto3
import logging
from typing import Dict, Any, Optional


logger = logging.getLogger()
logger.setLevel(logging.INFO)


def parse_dynamodb_image(image: Dict[str, Any]) -> Dict[str, Any]:
    """Extract values from DynamoDB Stream image format."""
    result = {}
    for key, value in image.items():
        result[key] = next(iter(value.values()))
    return result


def should_process_record(old_image: Optional[Dict[str, Any]], new_image: Dict[str, Any]) -> bool:
    """
    Determine if we should process this record.
    Returns True for:
    - New records (INSERT)
    - Updates where status changes to 'in_progress'
    """
    if old_image is None:
        logger.debug("New record, will process")
        return True
        
    old_status = old_image.get('status')
    new_status = new_image.get('status')
    
    if new_status == 'in_progress' and old_status != 'in_progress':
        logger.debug("Status changed to in_progress from %s, will process", old_status)
        return True
        
    logger.debug("No relevant changes (old_status=%s, new_status=%s), skipping", 
                old_status, new_status)
    return False


def lambda_handler(event: Dict[str, Any], context: Any) -> None:
    """Process DynamoDB Stream events and send them to SQS."""
    logger.info("Processing Stream event with %d records", len(event['Records']))
    logger.debug("Full event: %s", json.dumps(event))
    
    sqs = boto3.client('sqs')
    queue_url = os.environ['QUEUE_URL']

    for record in event['Records']:
        event_name = record['eventName']
        logger.info("Processing %s event", event_name)
        
        try:
            new_image = parse_dynamodb_image(record['dynamodb']['NewImage'])
            old_image = None
            if 'OldImage' in record['dynamodb']:
                old_image = parse_dynamodb_image(record['dynamodb']['OldImage'])
            
            logger.debug("Old image: %s", json.dumps(old_image) if old_image else "None")
            logger.debug("New image: %s", json.dumps(new_image))

            if event_name not in ('INSERT', 'MODIFY'):
                logger.debug("Skipping %s event", event_name)
                continue

            if not should_process_record(old_image, new_image):
                continue

            message = {
                'topic_id': new_image['topic_id'],
                'date': new_image['date'],
                'status': new_image.get('status'),
                'created_at': new_image.get('created_at'),
                'retry_count': new_image.get('retry_count', 0)
            }
            
            logger.info("Sending message to SQS for topic '%s' and date '%s' (retry %d)", 
                       message['topic_id'], 
                       message['date'],
                       message['retry_count'])
            
            response = sqs.send_message(
                QueueUrl=queue_url,
                MessageBody=json.dumps(message)
            )
            
            logger.info("Message sent successfully, MessageId: %s", 
                       response.get('MessageId'))

        except KeyError as e:
            logger.error(
                "Missing required field: %s. Record: %s",
                str(e),
                json.dumps(record),
                exc_info=True
            )
        except Exception as e:
            logger.error(
                "Error processing record: %s. Record: %s",
                str(e),
                json.dumps(record),
                exc_info=True
            )
