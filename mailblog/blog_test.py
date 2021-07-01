import unittest
import blog
import email
from email.policy import default


class BlogTest(unittest.TestCase):
    def test_base26(self):
        self.assertEqual(blog.base26(25), "z")
        self.assertEqual(blog.base26(26), "ba")
        self.assertEqual(blog.base26(27), "bb")

    def test_main(self):
        blog.memory_db()
        mail = email.message_from_string(
            """Date: Mon, 31 May 2021 20:02:04 +1000
From: Ian Haywood <ian@haywood.id.au>
To: world@blogs.com
Subject: Test Post
Content-Type: text/plain; charset=windows-1252; format=flowed
Content-Transfer-Encoding: 7bit
Content-Language: en-GB

# header

a markdown paragraph 
""",
            policy=default,
        )
        blog.process_mail(mail)


if __name__ == "__main__":
    unittest.main()
