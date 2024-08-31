from selenium import webdriver
from urllib.parse import urlparse
from os import path, getenv
from PIL import Image
from PIL import ImageDraw
from PIL import ImageOps
from io import BytesIO
from dotenv import load_dotenv
from math import ceil
import base64
import httpx
from httpx_socks import SyncProxyTransport
import argparse
import re
import sys
import sqlite3

DB = "sqlite3.db" 

FIREFOX_OPTIONS = webdriver.FirefoxOptions()
FIREFOX_OPTIONS.add_argument("--headless")
FIREFOX_OPTIONS.add_argument("--width=800")
FIREFOX_OPTIONS.add_argument("--height=700")

FIREFOX_PROFILE = webdriver.FirefoxProfile()
FIREFOX_PROFILE.set_preference('network.proxy.type', 1)
FIREFOX_PROFILE.set_preference('network.proxy.socks', "localhost")
FIREFOX_PROFILE.set_preference('network.proxy.socks_port', 10080)
FIREFOX_PROFILE.set_preference('network.proxy.socks_remote_dns', True)
FIREFOX_OPTIONS.profile = FIREFOX_PROFILE

TRANSPORT = SyncProxyTransport.from_url("socks5://localhost:10080")
CLIENT = httpx.Client(transport=TRANSPORT)

class Database:
    DB = "sqlite3.db"
    def __init__(self):
        self.conn = None

        if not path.exists("./sqlite3.db"):
            self.conn = self.connect_db()
            self.migrate_db()
        else:
            self.conn = self.connect_db()

    def __del__(self):
        self.conn = None

    def connect_db(self):
        return sqlite3.connect(DB)

    def migrate_db(self):
        self.conn.execute("DROP TABLE IF EXISTS soc_bot_log;")
        self.conn.execute("DROP TABLE IF EXISTS url;")
        self.conn.execute("DROP TABLE IF EXISTS webhook_url;")

        self.conn.execute("""CREATE TABLE soc_bot_log(
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            unit_id INTEGER,
            url TEXT,
            status_code TEXT,
            response_length INTEGER,
            base64_image TEXT,
            created_at TEXT NOT NULL DEFAULT (DATETIME('now', 'localtime'))
        );""")

        self.conn.execute("CREATE TABLE url(url TEXT PRIMARY KEY);")
        self.conn.execute("CREATE TABLE webhook_url(url TEXT PRIMARY KEY);")

    def get_urls(self):
        cur = self.conn.cursor()
        cur.execute("SELECT * FROM url;")
        urls = [url[0] for url in cur.fetchall() if re.match(r"^https?://.+", url[0])]
        return urls
    
    def get_latest_unit_id(self):
        cur = self.conn.cursor()
        cur.execute("SELECT MAX(unit_id) FROM soc_bot_log;")
        unit_id = cur.fetchone()[0]

        if not unit_id:
            return 0
        
        return unit_id
    
    def get_logs_by_unit_id(self, unit_id):
        cur = self.conn.cursor()
        sql = "SELECT * FROM soc_bot_log WHERE unit_id = ?;"
        data = (unit_id, )
        cur.execute(sql, data)
        return cur.fetchall()

    def get_logs_by_latest_unit_id(self):
        unit_id = self.get_latest_unit_id()
        logs = self.get_logs_by_unit_id(unit_id)
        return logs
    
    def insert_url(self, url):
        sql = "INSERT INTO url(url) VALUES (?);"
        data = (url, )
        try:
            self.conn.execute(sql, data)
            self.conn.commit()
        except sqlite3.IntegrityError as e:
            print("The URL is already registerd.")

    def delete_url(self, url):
        sql = "DELETE FROM url WHERE url = ?;"
        data = (url, )
        self.conn.execute(sql, data)
        self.conn.commit()

    def insert_log(self, unit_id, url, status_code, response_length, base64_image):
        sql = "INSERT INTO soc_bot_log(unit_id, url, status_code, response_length, base64_image) VALUES (?,?,?,?,?);"
        data = (unit_id, url, status_code, response_length, base64_image, )
        self.conn.execute(sql, data)
        self.conn.commit()

    def get_webhook_urls(self):
        cur = self.conn.cursor()
        cur.execute("SELECT * FROM webhook_url;")
        urls = [url[0] for url in cur.fetchall()]
        return urls

    def insert_webhook_url(self, url):
        sql = "INSERT INTO webhook_url(url) VALUES (?);"
        data = (url, )
        self.conn.execute(sql, data)
        self.conn.commit()

    def delete_webhook_url(self, url):
        sql = "DELETE FROM webhook_url WHERE url = ?;"
        data = (url, )
        self.conn.execute(sql, data)
        self.conn.commit()

def get_screenshot(driver, db, url, unit_id):
    img_bytes = BytesIO()

    try:
        driver.get(url.geturl())
        img_bytes = BytesIO(driver.get_screenshot_as_png())
        res = CLIENT.get(url.geturl())
        status_code = res.status_code
        response_length = len(res.content)
    except Exception as e:
        err_image = Image.new("RGB", (800,600), (255,0,0))
        draw = ImageDraw.Draw(err_image)
        draw.multiline_text(xy=(0,0), text=str(e), fill="black", font_size=36)
        err_image.save(img_bytes, format="PNG")
        status_code = 999
        response_length = 0
        # debug
        print(e)
        sys.exit()

    base = Image.new("RGB", (800,700), (0,0,0))
    screenshot = Image.open(img_bytes)
    base.paste(screenshot)
    draw = ImageDraw.Draw(base)
    draw.text(xy=(400,650), text=url.geturl(), fill="white", font_size=36, anchor="mm")
    borderd = ImageOps.expand(base, border=2, fill="white")

    edited_img_bytes = BytesIO()
    borderd.save(edited_img_bytes, format="PNG")
    
    b64_image = base64.b64encode(edited_img_bytes.getvalue())

    db.insert_log(unit_id, url.geturl(), status_code, response_length, b64_image)

def merge_images(db, unit_id):
    files = db.get_logs_by_unit_id(unit_id) 
    file_count = len(files)
    rows = 3
    columns = ceil(file_count / rows)
    width = 800
    height = 700

    grid_img = Image.new("RGB", (width*rows, height*columns), (0,0,0))

    for i,f in enumerate(files):
        decoded_img = BytesIO(base64.b64decode(f[5]))
        grid_img.paste(Image.open(decoded_img), (i%rows*width, i//rows*height))

    merged_image = BytesIO()
    grid_img.save(merged_image, format="PNG")

    return merged_image

def post_image_to_discord(db, image):
    image.name = "image.png"

    urls = db.get_webhook_urls()
    for url in urls:
        res = httpx.post(url, files={"file": image})
        assert res.status_code == 200

def parse_args():
    parser = argparse.ArgumentParser(description="Go to the URL in the text file, take a screenshot, and post it to the webhook URL.")
     
    arg_group = parser.add_mutually_exclusive_group()
    arg_group.add_argument("-a", "--add-url")
    arg_group.add_argument("-l", "--list-urls", action="store_true")
    arg_group.add_argument("-d", "--delete-url")
    arg_group.add_argument("-wa", "--add-webhook-url")
    arg_group.add_argument("-wl", "--list-webhook-url", action="store_true")
    arg_group.add_argument("-wd", "--delete-webhook-url")

    args = parser.parse_args()
    return args

def main():
    args = parse_args()
    db = Database()

    if args.add_url:
        if re.match(r"^https?://.+", args.add_url):
            db.insert_url(args.add_url)
            urls = db.get_urls()
            print(*urls, sep="\n")
            sys.exit()
        else:
            print(f"URL must start with 'http://' or 'https://': {arg.add_url}")
            sys.exit()
    elif args.list_urls:
        urls = db.get_urls()
        print(*urls, sep="\n")
        sys.exit()
    elif args.delete_url:
        db.delete_url(args.delete_url)
        urls = db.get_urls()
        print(*urls, sep="\n")
        sys.exit()
    elif args.add_webhook_url:
        db.insert_webhook_url(args.add_webhook_url)
        urls = db.get_webhook_urls()
        print(*urls, sep="\n")
        sys.exit()
    elif args.list_webhook_url:
        urls = db.get_webhook_urls()
        print(*urls, sep="\n")
        sys.exit()
    elif args.delete_webhook_url:
        db.delete_webhook_url(args.delete_webhook_url)
        urls = db.get_webhook_urls()
        print(*urls, sep="\n")
        sys.exit()


    urls = db.get_urls()
    unit_id = db.get_latest_unit_id() + 1
    driver = webdriver.Firefox(options=FIREFOX_OPTIONS)

    for url in urls:
        parsed_url = urlparse(url)
        assert re.match("^https?$", parsed_url.scheme)
        
        get_screenshot(driver, db, parsed_url, unit_id)

    driver.quit()

    image = merge_images(db, unit_id)
    post_image_to_discord(db, image)

if __name__ == "__main__":
    main()
    
