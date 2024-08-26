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
import argparse
import re
import sys
import sqlite3

DB = "sqlite3.db" 

CHROME_OPTIONS = webdriver.ChromeOptions()
CHROME_OPTIONS.add_argument("--headless")

def connect_db():
    return  sqlite3.connect(DB)

def db_init(conn):
    conn.execute("DROP TABLE IF EXISTS soc_bot_log;")
    conn.execute("DROP TABLE IF EXISTS url;")

    conn.execute("""CREATE TABLE soc_bot_log(
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        unit_id INTEGER,
        url TEXT,
        status_code TEXT,
        response_length INTEGER,
        base64_image TEXT,
        created_at TEXT NOT NULL DEFAULT (DATETIME('now', 'localtime'))
    );""")

    conn.execute("CREATE TABLE url(url TEXT PRIMARY KEY);")

def get_urls(conn):
    cur = conn.cursor()
    cur.execute("SELECT * FROM url;")
    urls = [url[0] for url in cur.fetchall()]

    return urls

def get_latest_unit_id(conn):
    cur = conn.cursor()
    cur.execute("SELECT MAX(unit_id) FROM soc_bot_log;")
    return cur.fetchone()[0]

def get_logs_by_unit_id(conn, unit_id):
    cur = conn.cursor()
    sql = "SELECT * FROM soc_bot_log WHERE unit_id = ?;"
    data = (unit_id, )
    cur.execute(sql, data)
    return cur.fetchall()

def parse_args():
    parser = argparse.ArgumentParser(description="Go to the URL in the text file, take a screenshot, and post it to the webhook URL.")

    parser.add_argument("-a", "--add-url")
    parser.add_argument("-l", "--list-urls")

    args = parser.parse_args()
    return args

def get_screenshot(driver, conn, url, unit_id):
    img_bytes = BytesIO()

    try:
        driver.get(url.geturl())
        img_bytes = BytesIO(driver.get_screenshot_as_png())
        res = httpx.get(url.geturl())
        status_code = res.status_code
        response_length = len(res.content)
    except Exception as e:
        err_image = Image.new("RGB", (800,600), (255,0,0))
        draw = ImageDraw.Draw(err_image)
        draw.multiline_text(xy=(0,0), text=str(e), fill="black", font_size=36)
        err_image.save(img_bytes, format="PNG")
        status_code = 999
        response_length = 0

    base = Image.new("RGB", (800,700), (0,0,0))
    screenshot = Image.open(img_bytes)
    base.paste(screenshot)
    draw = ImageDraw.Draw(base)
    draw.text(xy=(400,650), text=url.geturl(), fill="white", font_size=36, anchor="mm")
    borderd = ImageOps.expand(base, border=2, fill="white")

    edited_img_bytes = BytesIO()
    borderd.save(edited_img_bytes, format="PNG")

    b64_image = base64.b64encode(edited_img_bytes.getvalue())
    sql = "INSERT INTO soc_bot_log(unit_id, url, status_code, response_length, base64_image) VALUES (?,?,?,?,?);"
    data = (unit_id, url.geturl(), status_code, response_length, b64_image, )
    conn.execute(sql, data)
    conn.commit()

def merge_images(conn, unit_id):
    files = get_logs_by_unit_id(conn, unit_id) 
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

def post_image_to_discord(image):
    load_dotenv()
    url = getenv("WEBHOOK_URL")
    image.name = "image.png"

    #res = httpx.post(url, files={"file": image})
    #assert res.status_code == 200

if __name__ == "__main__":
    #args = parse_args()

    if not path.exists("./sqlite3.db"):
        conn = connect_db()
        db_init(conn)
    else:
        conn = connect_db()

    urls = get_urls(conn)
    unit_id = get_latest_unit_id(conn) + 1

    driver = webdriver.Chrome(CHROME_OPTIONS)
    for url in urls:
        parsed_url = urlparse(url)
        assert re.match("^https?$", parsed_url.scheme)
        
        get_screenshot(driver, conn, parsed_url, unit_id)

    driver.quit()

    image = merge_images(conn, unit_id)
    post_image_to_discord(image)
    
    conn.close()
