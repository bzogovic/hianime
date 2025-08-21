import os
import shutil
import time
from argparse import Namespace
from dataclasses import dataclass
from typing import Any
from tools.functions import get_int_in_range
from urllib.parse import urljoin

import requests
from bs4 import BeautifulSoup, Tag
from colorama import Fore
from selenium.webdriver.common.by import By
from selenium.webdriver.remote.webelement import WebElement
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.support.ui import WebDriverWait
from selenium_stealth import stealth
from seleniumwire import webdriver
import os
import re
import time
import sys
from typing import Any
from bs4 import BeautifulSoup
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium_stealth import stealth
from seleniumwire import webdriver
from yt_dlp import YoutubeDL
from tools.functions import get_int_in_range

class HianimeExtractor:
    def __init__(self, args):
        self.args = args
        self.HEADERS = {
            "User-Agent": "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36",
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
            "Accept-Language": "en-US,en;q=0.5",
            "Connection": "keep-alive",
        }
        self.BASE_URL = "https://hianime.to"
        self.output_dir = self.args.output_dir
        self._driver = None

    def configure_driver(self):
        # Use Chrome in headless mode
        options = webdriver.ChromeOptions()
        options.add_argument("--headless=new")
        options.add_argument("--disable-gpu")
        options.add_argument("--no-sandbox")
        options.add_argument("--window-size=1920,1080")
        options.add_argument(f"--user-agent={self.HEADERS['User-Agent']}")
        self._driver = webdriver.Chrome(options=options)
        stealth(self._driver,
            languages=["en-US", "en"],
            vendor="Google Inc.",
            platform="Win32",
            webgl_vendor="Intel Inc.",
            renderer="Intel Iris OpenGL Engine",
            fix_hairline=True,
        )

    def close_driver(self):
        if self._driver:
            self._driver.quit()
            self._driver = None

    def search_anime(self, query: str) -> list[dict[str, Any]]:
        import requests
        url = f"{self.BASE_URL}/search?keyword={query.replace(' ', '+')}"
        resp = requests.get(url, headers=self.HEADERS)
        soup = BeautifulSoup(resp.text, "html.parser")
        results = []
        for a in soup.select(".film_list-wrap .flw-item"):
            title_tag = a.select_one(".dynamic-name")
            link_tag = a.select_one("a")
            sub_ep_tag = a.select_one(".fd-infor .fdi-item")
            title = title_tag.get("title") if title_tag else "Unknown"
            link = str(link_tag.get("href")) if link_tag and link_tag.get("href") else None
            sub_episodes = sub_ep_tag.text if sub_ep_tag else "0"
            if link:
                results.append({
                    "name": title,
                    "url": self.BASE_URL + link,
                    "sub_episodes": int(re.sub(r'\D', '', sub_episodes) or "0"),
                    "dub_episodes": 0,
                })
        return results

    def get_anime(self):
        # Prompt user for anime name or link
        if self.args.link:
            return self.get_anime_from_link(self.args.link)
        query = input("Enter anime name: ")
        results = self.search_anime(query)
        if not results:
            print("No results found.")
            sys.exit(1)
        print("Select anime:")
        for i, r in enumerate(results):
            print(f"{i+1}. {r['name']} ({r['url']})")
        idx = get_int_in_range("Enter number: ", 1, len(results)) - 1
        return results[idx]

    def get_anime_from_link(self, link: str):
        import requests
        resp = requests.get(link, headers=self.HEADERS)
        soup = BeautifulSoup(resp.text, "html.parser")
        title_tag = soup.select_one("h2.film-name.dynamic-name")
        title = title_tag.text.strip() if title_tag else "Unknown"
        return {"name": title, "url": link, "sub_episodes": 0, "dub_episodes": 0}

    def get_episode_urls(self, anime_url: str, start_ep: int, end_ep: int) -> list[dict[str, Any]]:
        import requests
        resp = requests.get(anime_url, headers=self.HEADERS)
        soup = BeautifulSoup(resp.text, "html.parser")
        ep_links = []
        for a in soup.select(".episodes ul li a"):
            data_number = a.get("data-number", "0")
            try:
                ep_num = int(str(data_number))
            except Exception:
                continue
            href = str(a.get("href")) if a.get("href") else None
            if href and start_ep <= ep_num <= end_ep:
                ep_links.append({"ep": ep_num, "url": self.BASE_URL + href})
        if not ep_links:
            for a in soup.select(".detail-infor-content .item .epi a"):
                try:
                    ep_num = int(a.text.strip().replace("Episode ", ""))
                except Exception:
                    continue
                href = str(a.get("href")) if a.get("href") else None
                if href and start_ep <= ep_num <= end_ep:
                    ep_links.append({"ep": ep_num, "url": self.BASE_URL + href})
        return ep_links

    def extract_video_url(self, episode_url: str, max_retries: int = 3) -> str | None:
        # Use Selenium to load the episode page, find the iframe, load the iframe, and extract the video or m3u8 URL from the rendered DOM.
        import re
        if not self._driver:
            print("Selenium driver not initialized!")
            return None
        try:
            self._driver.get(episode_url)
            WebDriverWait(self._driver, 15).until(
                EC.presence_of_element_located((By.CSS_SELECTOR, "iframe"))
            )
            iframe = self._driver.find_element(By.CSS_SELECTOR, "iframe")
            self._driver.switch_to.frame(iframe)
            time.sleep(2)
            video_url = None
            try:
                video = self._driver.find_element(By.TAG_NAME, "video")
                video_url = video.get_attribute("src")
            except Exception:
                pass
            if not video_url:
                html = self._driver.page_source
                m3u8s = re.findall(r'(https?://[^\s"\']+\.m3u8)', html)
                if m3u8s:
                    video_url = m3u8s[0]
            self._driver.switch_to.default_content()
            return video_url
        except Exception as e:
            print(f"Failed to extract video url: {e}")
            return None

    def yt_dlp_download(self, url: str, headers: dict[str, str], location: str) -> bool:
        base_dir = os.path.join(self.output_dir, "one-piece")
        os.makedirs(base_dir, exist_ok=True)
        outtmpl = os.path.join(base_dir, os.path.basename(location)) + ".mp4"
        ydl_opts = {
            "outtmpl": outtmpl,
            "format": "bv*+ba/best",
            "merge_output_format": "mp4",
            "quiet": False,
            "no_warnings": True,
            "http_headers": headers,
        }
        try:
            with YoutubeDL(ydl_opts) as ydl:
                ydl.download([url])
            print(f"Downloaded to {outtmpl}")
            return True
        except Exception as e:
            print(f"yt-dlp failed: {e}")
            return False





