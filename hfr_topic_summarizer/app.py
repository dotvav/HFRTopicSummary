import logging
import boto3
from hfr import Topic
from datetime import date, datetime, timedelta


MESSAGE_COUNT_LIMIT = 1000

logger = logging.getLogger()
client = boto3.client('lambda')

def lambda_handler(event, context):
    cat = event["queryStringParameters"]["cat"]
    subcat = event["queryStringParameters"]["subcat"]
    post = event["queryStringParameters"]["post"]

    logger.info(f"Request received for cat={cat}, subcat={subcat}, post={post}")

    # Algo
    # * Générer la version imprimable ```&print=1```
    # * Trouver et charger la dernière page
    # * Enregistrer tous les message
    # * Remonter à la page précédente jusqu'à ce (qu'on trouve un message déjà connu ou) que la date soit < today - 1
    # * Préparer un doc contenant tous les messages
    # * Demander un résumé à Claude/Deepseek
    # * Retourner le résumé

    # Set dates up
    today = date.today()
    yesterday = today - timedelta(days=1)
    before_yesterday = today - timedelta(days=2)
    logger.debug(f"Today={today}, yesterday={yesterday}, before_yesterday={before_yesterday}")

    # Load the topic's first and last pages
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

    return {
        "isBase64Encoded": False,
        "statusCode": 200,
        "headers": { "Content-Type": "application/json" },
        "body": f"Messages count: {len(messages)}"
    }