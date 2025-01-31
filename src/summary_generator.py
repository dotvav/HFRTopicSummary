import os
import json
import boto3
import logging
from typing import Dict, Any
from hfr import Topic, Message
from datetime import datetime, timedelta, timezone
import re


MESSAGE_COUNT_LIMIT = 1000

logger = logging.getLogger()
log_level = os.environ.get('LOG_LEVEL', 'WARNING').upper()
try:
    logger.setLevel(getattr(logging, log_level))
except (AttributeError, TypeError):
    logger.setLevel(logging.WARNING)
    logger.warning(f"Invalid LOG_LEVEL '{log_level}', defaulting to WARNING")

bedrock_client = boto3.client("bedrock-runtime", region_name="eu-west-3")
#bedrock_model_id = "eu.anthropic.claude-3-5-sonnet-20240620-v1:0"
bedrock_model_id = "anthropic.claude-3-haiku-20240307-v1:0"

def extract_data_from_claude_response(text) -> dict:
    """Extract JSON from Claude's response that might contain additional text"""
    json_match = re.search(r'\{[\s\S]*\}', text)
    if json_match:
        json_string = json_match.group(0)
        try:
            return json.loads(json_string)
        except json.JSONDecodeError as e:
            logger.error(f"Invalid JSON format: {e}")
            return {
                "success": False,
                "error": str(e),
                "json_string": json_string,
            }
    return {
        "success": False,
        "error": "Can't find the data in the generated text.",
        "json_string": text,
    }

def should_process_summary(summaries_table, topic_id, date):
    """
    Check and update summary status based on complex conditions.
    Returns True if we should process this summary, False otherwise.
    """
    now = datetime.now(timezone.utc)
    one_hour_ago = now - timedelta(hours=1)
    
    try:
        response = summaries_table.update_item(
            Key={
                'topic_id': topic_id,
                'date': date
            },
            UpdateExpression='SET status = :new_status, last_updated = :now',
            ConditionExpression=(
                'attribute_not_exists(status) OR '                    # No record exists
                'status = :error_status OR '                         # Status is "error"
                '(status = :init_status AND last_updated < :stale)'  # Status "in_progress" but stale
            ),
            ExpressionAttributeValues={
                ':new_status': 'in_progress',
                ':error_status': 'error',
                ':init_status': 'in_progress',
                ':stale': one_hour_ago.isoformat(),
                ':now': now.isoformat()
            },
            ReturnValues='NONE'
        )
        return True  # Update succeeded, we should process

    except summaries_table.meta.client.exceptions.ConditionalCheckFailedException:
        # Update failed because conditions weren't met (completed or recent in_progress)
        return False

def get_messages(topic: Topic, summary_date_str) -> list[Message]:
    summary_date = datetime.strptime(summary_date_str, "%Y-%m-%d").date()    
    before_date = summary_date - timedelta(days=1)
    before_date_str = str(before_date)

    # Load the topic's first and last pages
    topic.load_page(1)
    logger.debug(f"Page 1 loaded, topic.max_page={topic.max_page}")
    if topic.max_page and topic.max_page > 1:
        topic.load_page(topic.max_page)
        logger.debug(f"Page {topic.max_page} loaded")
    
    # Find out what is the last message's date
    logger.debug(f"Topic's max_date={topic.max_date}")

    # If the last message date is after today 00:00, load previous pages until we have all of yesterday
    if topic.max_date >= str(summary_date_str):
        logger.debug(f"Have we fetched before yesterday? = {before_date_str in topic.messages.keys()}")
        page = topic.max_page - 1
        while page > 1 and not topic.has_date(before_date_str):
            logger.debug(f"Now loading page {page}")
            topic.load_page(page)
            page -= 1

    # Now extract the last `MESSAGE_COUNT_LIMIT` messages of yesterday
    if topic.has_date(summary_date_str):
        messages = topic.messages_on_date(summary_date_str)
        if len(messages) > MESSAGE_COUNT_LIMIT:
            messages = messages[-MESSAGE_COUNT_LIMIT:]
        logger.debug(f"Yesterday's messages count = {len(topic.messages_on_date(summary_date_str))}, selected messages {len(messages)}")
    else:
        logger.debug(f"No messages at date {summary_date_str}")
        messages = ()

    return messages

def get_prompt_template():
    current_dir = os.path.dirname(os.path.abspath(__file__))
    prompt_path = os.path.join(current_dir, 'prompts', 'summary_prompt.txt')
    with open(prompt_path, 'r') as f:
        return f.read()

def get_summary_data(topic: Topic, date_str: str, messages: list[Message]) -> dict:
    # Make a doc
    topic_data = json.dumps(
        {
            "title": topic.title,
            "date": date_str,
            "messages": [message.to_dict() for message in messages]
        },
        indent=4
    )

    # Submit the doc for summary
    bedrock_request = {
        "modelId": bedrock_model_id,
        "body": json.dumps({
            "anthropic_version": "bedrock-2023-05-31",
            "max_tokens": 1000,
            "temperature": 0.3,
            "messages": [
                {
                    "role": "user",
                    "content": get_prompt_template() + "\n" + json.dumps(topic_data, indent=4)
                }
            ],
        })}
    try:
        bedrock_response = bedrock_client.invoke_model(**bedrock_request)
        response_body = json.loads(bedrock_response['body'].read())
        bedrock_data = response_body['content'][0]['text']
        bedrock_data = extract_data_from_claude_response(bedrock_data)
    except Exception as e:
        logger.error(e)
        bedrock_data = {
            "success": False,
            "error": str(e),
            "json_string": json.dumps(bedrock_request),
        }

    logger.debug(bedrock_data)
                    
    return bedrock_data


def lambda_handler(event: Dict[str, Any], context: Any) -> None:
    """Process messages from SQS and generate summaries."""
    logger.info("Processing SQS event: %s", json.dumps(event))

    dynamodb = boto3.resource('dynamodb')
    topics_table = dynamodb.Table(os.environ['TOPICS_TABLE'])
    messages_table = dynamodb.Table(os.environ['MESSAGES_TABLE'])
    summaries_table = dynamodb.Table(os.environ['SUMMARIES_TABLE'])

    for record in event['Records']:
        message = json.loads(record['body'])
        topic_id = message['topic_id']
        date_str = message['date']

        try:
            logger.info("Processing summary for topic: %s, date: %s", topic_id, date_str)
            (cat, subcat, post) = str.split(topic_id, "#")
            topic = Topic(cat, subcat, post)
            messages = get_messages(topic, date_str)

            if messages:
                summary_data = get_summary_data(topic, date_str, messages)

                if summary_data["success"]:
                    # Store the summary in the table and update the status
                    new_summary = {
                        "topic_id": topic_id,
                        "date": date_str,
                        "status": "completed",
                        "last_updated": datetime.now(timezone.utc).isoformat(),
                        "summary": summary_data["summary"]
                    }
                    summaries_table.put_item(Item=new_summary)
                else:
                    new_summary = {
                        "topic_id": topic_id,
                        "date": date_str,
                        "status": "error",
                        "last_updated": datetime.now(timezone.utc).isoformat(),
                        "summary": "Une erreur est survenue",
                        "error_details": summary_data.get("error", "An unknown error has occured")
                    }
                    summaries_table.put_item(Item=new_summary)

            else:
                # When there are no messages to summarize, store a short information
                new_summary = {
                    "topic_id": topic_id,
                    "date": date_str,
                    "status": "completed",
                    "last_updated": datetime.now(timezone.utc).isoformat(),
                    "summary": "Aucun message"
                }
                summaries_table.put_item(Item=new_summary)

        except Exception as e:
            logger.error(
                "Error processing message: %s. Message: %s",
                str(e),
                json.dumps(message),
                exc_info=True
            )
            # Let the message return to queue (if within retry limit)
            raise
