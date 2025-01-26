"""HFR"""

from datetime import datetime
from bs4 import BeautifulSoup, NavigableString
from typing import Any
import re
from sortedcontainers import SortedList
import logging
import requests


logger = logging.getLogger()
logger.setLevel("DEBUG")

class Topic:
    
    def __init__(self, cat: int, subcat: int, post: int) -> None:
        self.cat = cat
        self.subcat = subcat
        self.post = post
        self.messages = dict()

    def first_messages(self, limit: int = 40) -> list[datetime]:
        return self.messages[0:limit-1]

    def last_messages(self, limit: int = 40) -> list[datetime]:
        return self.messages[-limit:0]

    def last_update_date(self) -> datetime:
        return self.messages[-1].timestamp

    def parse_page_html(self, html: str) -> None:
        soup = BeautifulSoup(html, 'html.parser')
        self.title = soup.find("h3").text

        # Find highest page number
        pages_block = soup.find("tr", class_="fondForum2PagesHaut")
        pages_links = pages_block.find_all("a", href=re.compile(f"^/forum2.php?config=hfr.inc&amp;cat={self.cat}&amp;subcat={self.subcat}&amp;post={self.post}&amp;page=.*"))
        max_page = 1
        for page in pages_links:
            href = page.attrs["href"]
            for param in href.split("?")[1].split("&"):
                kv = param.split("=")
                if kv[0] == "page":
                    if kv[1] > max_page:
                        max_page = kv[1]
                    break
        self.max_page = max_page

        # Find all messages in the page
        messages_soup = soup.find_all("table", class_="messagetable")
        for message_block in messages_soup:
            message = Message.parse_html(self, message_block)
            if message:
                self.add_message(message)
    
    def add_message(self, message) -> None:
        date = message.timestamp.replace(hour=0, minute=0, second=0, microsecond=0)
        
        if date in self.messages:
            messages_for_date = self.messages[date]
        else:
            messages_for_date = SortedList([], key=lambda m: m.timestamp)
            self.messages[date] = messages_for_date
        messages_for_date.add(message)

    def load_page(self, page: int) -> None:
        url = f"https://forum.hardware.fr/forum2.php?config=hfr.inc&cat={self.cat}&subcat={self.subcat}&post={self.post}&print=1&page={page}"

        r = requests.get(url, headers={"Accept": "text/html", "Accept-Encoding": "gzip, deflate, br, zstd", "User-Agent": "HFRTopicSummarizer"})
        html = r.text

        self.parse_page_html(html)



class Message:
    def __init__(self, topic: Topic, id: int, timestamp: datetime, author:str, text: str) -> None:
        self.topic = topic
        self.id = id
        self.timestamp = timestamp
        self.author = author
        self.text = text
    
    @classmethod
    def parse_html(cls, topic: Topic, html: NavigableString):
        case1 = html.find("td", class_="messCase1")

        author = case1.find("b", class_="s2").string
        if author == "Publicité":
            return None
        
        id = case1.find("a", rel="nofollow").attrs["href"][2:]

        case2 = html.find("td", class_="messCase2")
        timestamp_str = case2.find("div", class_="toolbar").find("div", class_="left").string
        logger.info(f"=== {timestamp_str} ===")

        timestamp = Message.parse_timestamp(timestamp_str)

        text = case2.find("div", id=f"para{id}").string

        return cls(topic, id, timestamp, author, text)
    
    @staticmethod
    def parse_timestamp(timestamp_str: str) -> datetime:
        d = timestamp_str[9:19]
        t = timestamp_str[22:30]
        return datetime.strptime(f"{d} {t}", "%d-%m-%Y %H:%M:%S")

