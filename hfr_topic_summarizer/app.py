import logging
import boto3
import requests
import re
from hfr import Topic

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

    topic = Topic(cat, subcat, post)
    topic.load_page(1)
    if topic.max_page and topic.max_page > 1:
        topic.load_page(topic.max_page)

    logger.info(topic.messages)

    return {
        "isBase64Encoded": False,
        "statusCode": 200,
        "headers": { "Content-Type": "application/json" },
        "body": "x"
    }