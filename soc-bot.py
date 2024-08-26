from selenium import webdriver
from urllib.parse import urlparse
from os import path
import argparse
import re
import sys
import os
import math

URL = "https://www.google.com"

CHROME_OPTIONS = webdriver.ChromeOptions()
CHROME_OPTIONS.add_argument("--headless")


def parse_args():
    parser = argparse.ArgumentParser(description="Go to the URL in the CSV file, take a screenshot, and post it to the webhook URL.")

    url_option = parser.add_mutually_exclusive_group(required=True)
    url_option.add_argument("-f", "--filename")
    url_option.add_argument("-u", "--url")

    parser.add_argument("-t", "--timeout", default=10)

    args = parser.parse_args()
    return args

def get_screenshot(driver, url):
    driver.get(url.geturl())
    filename = f"./screenshots/[{url.scheme}]{url.hostname}.png"
    driver.save_screenshot(filename)

    from PIL import Image
    from PIL import ImageDraw
    from PIL import ImageOps

    base = Image.new("RGB", (800,700), (0,0,0))
    screenshot = Image.open(filename)
    base.paste(screenshot)
    draw = ImageDraw.Draw(base)
    draw.text(xy=(400,650), text=url.geturl(), fill="white", font_size=36, anchor="mm")
    borderd = ImageOps.expand(base, border=2, fill="white")
    borderd.save(filename)

def merge_images():
    files = [f for f in os.listdir("./screenshots") if f not in "merged.png"]
    file_count = len(os.listdir("./screenshots"))
    rows = 3
    columns = math.ceil(file_count / rows)
    width = 800
    height = 700

    from PIL import Image
    grid_img = Image.new("RGB", (width*rows, height*columns), (0,0,0))

    for i,f in enumerate(files):
        grid_img.paste(Image.open(f"./screenshots/{f}"), (i%rows*width, i//rows*height))

    grid_img.save("./screenshots/merged.png")
    image = open("./screenshots/merged.png", "rb")

    for f in [f for f in os.listdir("./screenshots") if f not in "merged.png"]:
        os.remove(f"./screenshots/{f}")

    return image

def post_image_to_discord(image):
    import httpx

    URL = ""
    httpx.post(URL, files={"file": image})
    

if __name__ == "__main__":
    args = parse_args()

    if args.url != None:
        url = urlparse(args.url)
        assert re.match("^http?s$", url.scheme)

        driver = webdriver.Chrome(CHROME_OPTIONS)
        sys.exit()

    if args.filename != None:
        assert path.exists(args.filename)
        urls = open(args.filename, "r").readlines()
        driver = webdriver.Chrome(CHROME_OPTIONS)

        for url in urls:
            parsed_url = urlparse(url)
            assert re.match("^https?$", parsed_url.scheme)
            
            get_screenshot(driver, parsed_url)

        driver.quit()

        image = merge_images()
        post_image_to_discord(image)
