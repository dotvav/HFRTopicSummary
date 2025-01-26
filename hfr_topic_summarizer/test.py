from hfr import Topic, Message

html = open("samples/topic_page.html").read()

topic = Topic(cat=13, subcat=422, post=108102)
topic.parse_page_html(html)