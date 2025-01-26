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
    # * Enregistrer chaque les message
    # * Remonter à la page précédente jusqu'à ce qu'on trouve un message déjà connu ou que la doite soit < today - 1
    # * Préparer un doc contenant tous les messages
    # * Demander un résumé à Claude
    # * Retourner le résumé

    url = f"https://forum.hardware.fr/forum2.php?config=hfr.inc&cat={cat}&subcat={subcat}&post={post}&print=1&page=1"

    r = requests.get(url, headers={"Accept": "text/html", "Accept-Encoding": "gzip, deflate, br, zstd", "User-Agent": "HFRTopicSummarizer"})
    body = r.text

    topic = Topic(cat, subcat, post)
    topic.parse_page_html(body)

    return {
        "isBase64Encoded": False,
        "statusCode": 200,
        "headers": { "Content-Type": "application/json" },
        "body": "x"
    }