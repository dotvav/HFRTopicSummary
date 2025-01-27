import logging
import boto3
from hfr import Topic
from datetime import datetime, timedelta


MESSAGE_COUNT_LIMIT = 1000

logger = logging.getLogger()
logger.setLevel(logging.INFO)
client = boto3.client('lambda')

def lambda_handler(event, context):
    cat = event["queryStringParameters"]["cat"]
    subcat = event["queryStringParameters"]["subcat"]
    post = event["queryStringParameters"]["post"]

    # Algo
    # * Générer la version imprimable ```&print=1```
    # * Trouver et charger la dernière page
    # * Enregistrer tous les message
    # * Remonter à la page précédente jusqu'à ce qu'on trouve un message déjà connu ou que la date soit < today - 1
    # * Préparer un doc contenant tous les messages
    # * Demander un résumé à Claude
    # * Retourner le résumé

    # Set dates up
    today = datetime.today().replace(hour=0, minute=0, second=0, microsecond=0)
    yesterday = today - timedelta(days=1)
    before_yesterday = today - timedelta(days=2)
    logger.info(f"Today={today}, yesterday={yesterday}, before_yesterday={before_yesterday}")

    # Load the topic's first and last pages
    topic = Topic(cat, subcat, post)
    topic.load_page(1)
    logger.info(f"Page 1 loaded, topic.max_page={topic.max_page}")
    if topic.max_page and topic.max_page > 1:
        topic.load_page(topic.max_page)
        logger.info(f"Page {topic.max_page} loaded")
    
    # Find out what is the last message's date
    max_date = max(topic.messages.keys())
    logger.info(f"max_date={max_date}")


    # If the last message date is after today 00:00, load previous pages until we have all of yesterday
    if max_date > today.timestamp():
        page = topic.max_page - 1
        while page > 1 and before_yesterday.timestamp() not in topic.messages.keys():
            logger.info("Now loading page {page}")
            topic.load_page(page)
            page -= 1

    # Now extract the last `MESSAGE_COUNT_LIMIT` messages of yesterday
    if yesterday.timestamp() in topic.messages.keys():
        messages = topic.messages[yesterday.timestamp()][-1:-MESSAGE_COUNT_LIMIT]
    else:
        messages = ()

    return {
        "isBase64Encoded": False,
        "statusCode": 200,
        "headers": { "Content-Type": "application/json" },
        "body": f"Messages count: {len(messages)}"
    }