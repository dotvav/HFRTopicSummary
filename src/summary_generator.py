import os
import json
import boto3
import logging
from typing import Dict, Any
from hfr import Topic
from datetime import date, datetime, timedelta


MESSAGE_COUNT_LIMIT = 1000

logger = logging.getLogger()
logger.setLevel(logging.INFO)

def lambda_handler(event: Dict[str, Any], context: Any) -> None:
    """Process messages from SQS and generate summaries."""
    logger.info("Processing SQS event: %s", json.dumps(event))

    dynamodb = boto3.resource('dynamodb')
    topics_table = dynamodb.Table(os.environ['TOPICS_TABLE'])
    messages_table = dynamodb.Table(os.environ['MESSAGES_TABLE'])
    summaries_table = dynamodb.Table(os.environ['SUMMARIES_TABLE'])

    for record in event['Records']:
        try:
            message = json.loads(record['body'])
            topic_id = message['topic_id']
            date = message['date']

            logger.info("Processing summary for topic: %s, date: %s", topic_id, date)

            # Set dates up
            today = date.today()
            yesterday = today - timedelta(days=1)
            before_yesterday = today - timedelta(days=2)
            logger.debug(f"Today={today}, yesterday={yesterday}, before_yesterday={before_yesterday}")

            # Load the topic's first and last pages
            (cat, subcat, post) = str.split(topic_id, "#")
            topic = Topic(cat, subcat, post)
            topic.load_page(1)
            logger.debug(f"Page 1 loaded, topic.max_page={topic.max_page}")
            if topic.max_page and topic.max_page > 1:
                topic.load_page(topic.max_page)
                logger.debug(f"Page {topic.max_page} loaded")
            
            # Find out what is the last message's date
            logger.debug(f"Topic's max_date={topic.max_date}")

            # If the last message date is after today 00:00, load previous pages until we have all of yesterday
            if topic.max_date >= str(today):
                logger.debug(f"Have we fetched before yesterday? = {str(before_yesterday) in topic.messages.keys()}")
                page = topic.max_page - 1
                while page > 1 and not topic.has_date(str(before_yesterday)):
                    logger.debug(f"Now loading page {page}")
                    topic.load_page(page)
                    page -= 1

            # Now extract the last `MESSAGE_COUNT_LIMIT` messages of yesterday
            if topic.has_date(str(yesterday)):
                logger.debug(f"Yesterday's messages count = {len(topic.messages[str(yesterday)])}")
                messages = topic.messages_on_date(str(yesterday))[-1:-MESSAGE_COUNT_LIMIT]
            else:
                logger.debug(f"No messages at date {str(yesterday)}")
                messages = ()

            # TODO Make a doc
            # TODO Submit the doc for summary
            # TODO Store the summary in the table and update the status

        except Exception as e:
            logger.error(
                "Error processing message: %s. Message: %s",
                str(e),
                json.dumps(message),
                exc_info=True
            )
            # Let the message return to queue (if within retry limit)
            raise
