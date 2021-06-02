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
from sqlalchemy import create_engine, Column, String, DateTime, Integer, Boolean
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker


PUBLIC_HTML = os.path.expanduser("~/public_html")
ROOT = os.path.expanduser("~/preserve/blog")
URL = "/blog"

lu = TemplateLookup(directories=[ROOT])

mdp = markdown.Markdown(extensions=["meta"])


Session = sessionmaker()
Base = declarative_base()


class User(Base):
    __tablename__ = "users"
    id = Column(Integer, primary_key=True)
    email = Column(String)
    name = Column(String)
    images = Column(Boolean, default=False)
    payment_token = Column(String)
    crypto_token = Column(String)
    created = Column(DateTime, default=datetime.datetime.now)
    author = Column(String)


class Post(Base):
    __tablename__ = "posts"
    id = Column(Integer, primary_key=True)
    email = Column(String)
    name = Column(String)
    content = Column(String)
    time = Column(DateTime)
    keywords = Column(String)
    toot_id = Column(String)
    subject = Column(String)

    def fname(self):
        s = self.subject.lower().strip().replace(" ", "_")
        s = re.sub(r"\W+", "", s).replace("_", "-")
        return "%s-%s.html" % (s, base26(self.id))

    def url(self):
        return os.path.join(URL, self.fname())

    def strftime(self, fmt):
        return self.time.strftime(fmt)


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


def file_db():
    engine = create_engine("sqlite:///" + os.path.join(ROOT, "blog.db"))
    Session.configure(bind=engine)


def memory_db():
    engine = create_engine("sqlite://")
    Session.configure(bind=engine)
    Base.metadata.create_all(engine)


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


def delete_account(email):
    s = Session()
    u = s.query(User).filter_by(email=email).one()
    p = os.path.join(PUBLIC_HTML, u.name)
    for i in os.listdir(p):
        os.unlink(os.path.join(p, i))
    os.rmdir(p)
    s.delete(u)
    s.query(Post).filter_by(email=email).delete()
    s.commit()


def get_account(from_):
    s = Session()
    author, email = parseaddr(from_)
    u = s.query(User).filter_by(email=email).one_or_none()
    if u:
        return (u, False)
    a, b = email.split("@")
    c = b.split(".")
    name1 = a
    name2 = "%s_%s" % (a, c[0])
    name3 = "%s_1" % a
    name4 = "%s_%s" % (a, b)
    for n in [name1, name2, name3, name4]:
        u = s.query(User).filter_by(name=n).one_or_none()
        if not u:
            u = User(email=email, name=n, author=author)
            s.add(u)
            s.commit()
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
    t = parsedate_to_datetime(mail["Date"])
    p = Post(email=u.email, name=u.name, time=t, content=html, subject=mail["Subject"])
    s = Session()
    s.add(p)
    s.commit()


def emit_for_user(u):
    s = Session()
    q = s.query(Post).filter_by(name=u.name).order_by(Post.time)
    docs = list(q.all())
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
            "/page.html",
            u.name,
            doc.fname(),
            doc=doc,
            prev=prev,
            next=next,
            title=doc.subject,
            tags=doc.keywords,
            author=u.author,
            atom_url=os.path.join(URL, u.name, "feed.xml"),
        )
    write_file(
        "/index.html",
        u.name,
        "index.html",
        docs=docs,
        title="Articles",
        tags="blog",
        author=u.author,
        atom_url=os.path.join(URL, u.name, "feed.xml"),
    )
    write_file(
        "/user-feed.xml", u.name, "feed.xml", docs=docs, author=u.author, name=u.name
    )
    docs = (
        s.query(Post, User)
        .join(User.email == Post.email)
        .order_by(Post.time)
        .limit(20)
        .all()
    )
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
    s = Session()
    docs = (
        s.query(User, Post)
        .join(User.email == Post.email)
        .sort_by(User.c.created, Post.c.time)
        .limit(20)
        .all()
    )
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


#    mail = message_from_binary_file(f, policy=default)
