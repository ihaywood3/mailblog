#!/usr/bin/python3
import os
import os.path
import time
import datetime
from email import message_from_binary_file
from email.policy import default
from email.utils import parseaddr, parsedate_to_datetime
import sys
import re
from html.parser import HTMLParser
import html
import io

import markdown
from mako.lookup import TemplateLookup
import trivial_orm

PUBLIC_HTML = os.path.expanduser("~/public_html")
ROOT = os.path.expanduser("~/preserve/mailblog/")
URL = "/blog"

lu = TemplateLookup(directories=[ROOT])

mdp = markdown.Markdown(extensions=["meta"])

os.umask(0o022)  # postfix sets umask to odd value

SCHEMA = """
create table users (
    email text,
    name text,
    images text,
    payment_token text,
    crypto_token text,
    created timestamp,
    author text ); 


create table posts (
    rowid integer primary key,
    post_email text,
    content text,
    "time" timestamp,
    keywords text,
    toot_id text,
    subject text ); 

create view vwposts as
select * from users, posts where email = post_email; 
"""


class Post:
    def __init__(self, row):
        self.row = row

    def __getitem__(self, key):
        return self.row[key]

    def fname(self):
        s = self.row["subject"].lower().strip().replace(" ", "_")
        s = re.sub(r"\W+", "", s).replace("_", "-")
        return "%s-%s.html" % (s, base26(self.row["rowid"]))

    def url(self):
        return os.path.join(URL, self.row["name"], self.fname())

    def strftime(self, fmt):
        return self.row["time"].strftime(fmt)


ALLOWED_TAGS = {"a", "p", "i", "b", "ul", "li", "h1", "h2", "h3", "h4", "h5"}


class _MyHTMLParser(HTMLParser):
    def __init__(self):
        HTMLParser.__init__(self)
        self.html = io.StringIO()
        self.ignore = 0

    def handle_starttag(self, tag, attrs):
        if tag in ALLOWED_TAGS:
            self.html.write("<" + tag)
            if tag == "a":
                for n, v in attrs:
                    if n == "href":
                        self.html.write(' href="%s"' % v)
            self.html.write(">")
        if tag in ["script", "template", "style"]:
            self.ignore += 1

    def handle_endtag(self, tag):
        if tag in ["script", "template", "style"]:
            self.ignore -= 1
        if tag in ALLOWED_TAGS:
            self.html.write("</%s>" % tag)

    def handle_data(self, data):
        if self.ignore == 0:
            self.html.write(html.escape(data))


def _html_parse(html):
    parser = _MyHTMLParser()
    parser.feed(html)
    parser.close()
    return parser.html.getvalue()


def base26(n):
    if n > 0:
        return base26(n // 26) + chr(97 + (n % 26))
    else:
        return ""


db = None


def file_db():
    global db
    db = trivial_orm.SqliteWrapper(os.path.join(ROOT, "blog.db"))


def memory_db():
    global db
    db = trivial_orm.SqliteWrapper()
    db.db.executescript(SCHEMA)


def write_file(templ, sdir, fname, **kwargs):
    if sdir:
        p = os.path.join(PUBLIC_HTML, sdir)
        if not os.path.exists(p):
            os.mkdir(p)
        p = os.path.join(p, fname)
    else:
        p = os.path.join(PUBLIC_HTML, fname)
    with open(p, "w") as fd:
        fd.write(lu.get_template(templ).render(**kwargs))


def delete_account(name):
    u = db.select("users", name=name).fetchone()
    p = os.path.join(PUBLIC_HTML, u["name"])
    for i in os.listdir(p):
        os.unlink(os.path.join(p, i))
    os.rmdir(p)
    db.delete("users", name=name)
    db.delete("posts", post_email=u["email"])


def get_account(from_):
    author, email = parseaddr(from_)
    u = db.select("users", email=email).fetchone()
    if u:
        return (u, False)
    a, b = email.split("@")
    c = b.split(".")
    name1 = a
    name2 = "%s_%s" % (a, c[0])
    name3 = "%s_1" % a
    name4 = "%s_%s" % (a, b)
    for n in [name1, name2, name3, name4]:
        u = db.select("users", name=n).fetchone()
        if not u:
            u = dict(
                email=email, name=n, author=author, created=datetime.datetime.now()
            )
            db.insert("users", **u)
            return (u, True)


def mail2post(mail, u):
    html = plain = None
    for part in mail.walk():
        if part.get_content_type() == "text/html":
            html = part.get_content()
            if type(html) is bytes:
                c = part.get_charset() or "us-ascii"
                html = str(html, c, "ignore")
        elif part.get_content_type() == "text/plain":
            plain = part.get_content()
            if type(plain) is bytes:
                c = part.get_charset() or "us-ascii"
                plain = str(plain, c, "ignore")
    if html is None and plain is None:
        raise Exception("no text or html")
    if html:
        html = _html_parse(html)
    else:
        html = mdp.convert(plain)
    t = parsedate_to_datetime(mail["Date"]).replace(tzinfo=None)
    db.insert(
        "posts", post_email=u["email"], time=t, content=html, subject=mail["Subject"]
    )


def emit_for_user(u):
    docs = [
        Post(i)
        for i in db.db.execute(
            'select * from vwposts where email = ? order by "time"', (u["email"],)
        )
    ]
    for i in range(len(docs)):
        doc = docs[i]
        if i > 0:
            prev = docs[i - 1]
        else:
            prev = None
        if i < len(docs) - 1:
            next = docs[i + 1]
        else:
            next = None
        write_file(
            "page.html",
            u["name"],
            doc.fname(),
            doc=doc,
            prev=prev,
            next=next,
            title=doc["subject"],
            tags=doc["keywords"],
            author=u["author"],
            atom_url=os.path.join(URL, u["name"], "feed.xml"),
            index_url=os.path.join(URL, u["name"], "index.html"),
        )
    write_file(
        "/index.html",
        u["name"],
        "index.html",
        docs=docs,
        title="Articles for %s's blog" % u["author"],
        tags="blog",
        author=u["author"],
        atom_url=os.path.join(URL, u["name"], "feed.xml"),
    )
    write_file(
        "/user-feed.xml",
        u["name"],
        "feed.xml",
        docs=docs,
        author=u["author"],
        name=u["name"],
    )
    docs = [
        Post(i) for i in db.db.execute('select * from vwposts order by "time" limit 20')
    ]
    write_file(
        "main.html",
        None,
        "index.html",
        docs=docs,
        author="Ian Haywood",
        title="Main Page",
        tags="blog",
    )


def new_users_feed():
    docs = [
        Post(i)
        for i in db.db.execute('select * from vwposts order by created,"time" limit 20')
    ]
    write_file(
        "new-feed.xml",
        None,
        "new-feed.xml",
        docs=docs,
    )


def process_mail(mail):
    u, new = get_account(mail["From"])
    mail2post(mail, u)
    emit_for_user(u)
    if new:
        new_users_feed()


if __name__ == "__main__":
    file_db()
    cmd = sys.argv[1]
    if cmd == "mail":
        mail = message_from_binary_file(sys.stdin.buffer, policy=default)
        process_mail(mail)
    elif cmd == "del":
        delete_account(sys.argv[2])
    elif cmd == "create":
        db.db.executescript(SCHEMA)
    db.db.commit()
