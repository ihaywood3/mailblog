# mailblog

blog posts by sending emails to a nominated address. 

## Installation 

    pip install mailblog

If you want to modify code or templates, you need "development mode"

    git clone https://github.com/ihaywood3/mailblog
	cd mailblog
	pip install -e .

This provides a command `mailblog`, run `mailblog -h` to see the full 
options. 

### Database

`mailblog` uses a SQLite database, which must be initialised: `mailblog create`.

## Mailserver

Your system's mailserver must be configured to run the command `mailblog mail`
and send the incoming e-mail on standard input when an e-mail is sent to the address you 
want to associate with the blogging service.

I use `maildrop`, the relevant part of my recipe is:

    if (/^To:.*world@haywood.id.au/)
    {
	    cc $HOME/Mail/.World
	    to "|mailblog mail"
    }
	
	
**NOTE:** `mailblog` itself will accept an e-mail from anyone on the Internet and create 
a blog for them. Consequently you need either a spam filter or a fixed list of allowed senders
that it is checked before `mailblog mail` is run. I have written a Bayesian spam filter 
in Python: [`spamprobe.py`](https://github.com/ihaywood3/spamprobe.py)

## Webserver

`mailblog` does not serve Web pages, it generates HTML files and writes to a directory 
(by default `$HOME/public_html` but can be changed with the `-o` option. 

A webserver must then be configured to serve these files under the URL path `/blog/` 
This can't be changed currently. 

Here is my Apache configuration:

	Alias /blog /home/ian/public_html
	<Directory /home/ian/public_html >
		order allow,deny
		allow from all
	</Directory>

### CSS

The generated HTML loads its stylesheet from `blog/style.css`.  A basic `style.css` is 
provided in the source repository, this, or your own stylesheet, must be copied to the Web 
directory. 

## Demonstration Server

This is running [here](https://haywood.id.au/)
