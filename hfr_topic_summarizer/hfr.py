"""HFR"""

from datetime import datetime
from bs4 import BeautifulSoup, NavigableString
from typing import Any
import re
from sortedcontainers import SortedList
import logging


logger = logging.getLogger()
logger.setLevel("DEBUG")

class Topic:
    
    def __init__(self, cat: int, subcat: int, post: int) -> None:
        self.cat = cat
        self.subcat = subcat
        self.post = post
        self.messages = SortedList([], key=lambda x: x.timestamp)

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
        messages = soup.find_all("table", class_="messagetable")
        for message_block in messages:
            message = Message.parse_html(self, message_block)
            self.messages.add(message)




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

        author = case1.find("b", class_="s2").string # TODO remove 'breaking spaces'
        id = case1.find("a",  rel="nofollow").attrs["href"][2:]

        case2 = html.find("td", class_="messCase2")
        timestamp_str = case2.find("div", class_="toolbar").find("div", class_="left").string
        logger.info(f"=== {timestamp_str} ===")

        timestamp = Message.parse_timestamp(timestamp_str)

        text = case2.find("div", id=f"para{id}").string

        return cls(topic, id, timestamp, author, text)
    
    @staticmethod
    def parse_timestamp(timestamp_str: str) -> datetime:
        m = re.search(r"Post. le (\d\d-\d\d-\d\d\d\d)&nbsp;.&nbsp;(\d\d:\d\d:\d\d)&nbsp;&nbsp;", timestamp_str)
        return datetime.strptime(f"{m.group(1)} {m.group(2)}", "%d-%m-%Y %H:%M:%S")

