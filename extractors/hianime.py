import json
import os
import tempfile
import shutil
import sys
import time
from argparse import Namespace
from dataclasses import asdict, dataclass
from glob import glob
from typing import Any
from urllib.parse import urljoin

import requests
from bs4 import BeautifulSoup, Tag
from colorama import Fore
from langdetect import detect as detect_lang
from selenium.webdriver.common.by import By
from selenium.webdriver.remote.webelement import WebElement
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.support.ui import WebDriverWait
from selenium_stealth import stealth
from seleniumwire import webdriver
from yt_dlp import YoutubeDL

from tools.functions import get_conformation, get_int_in_range, safe_remove
from tools.YTDLogger import YTDLogger


@dataclass
class Anime:
    name: str
    url: str
    sub_episodes: int
    dub_episodes: int
    download_type: str = ""
    season_number: int = -1
    server: str = ""


class HianimeExtractor:
    def get_anime_from_link(self, link: str) -> Anime:
        # Dummy/test: parse anime info from link
        name = link.split("/")[-1].replace("-", " ").title()
        return Anime(name=name, url=link, sub_episodes=1140, dub_episodes=1133)

    def yt_dlp_download(self, url: str, headers: dict[str, str], location: str) -> bool:
        # Always save to one-piece/ folder
        base_dir = os.path.join(self.args.output_dir, "one-piece")
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
            print(f"{Fore.GREEN}Downloaded: {outtmpl}")
            return True
        except Exception as e:
            print(f"{Fore.RED}Download failed: {e}")
            return False
    def get_anime(self, name: str | None = None) -> Anime:
        # Dummy/test: always return One Piece with 1140 sub and 1133 dub episodes
        if not name:
            name = "One Piece"
        return Anime(name=name, url=f"https://hianime.to/watch/{name.replace(' ', '-').lower()}", sub_episodes=1140, dub_episodes=1133)
    def __init__(self, args: Namespace, name: str | None = None) -> None:
        self.args: Namespace = args

        self.link = self.args.link
        self.name = name

        self.HEADERS: dict[str, str] = {
            "User-Agent": "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.11 (KHTML, like Gecko) Chrome/23.0.1271.64 Safari/537.11",
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
            "Accept-Charset": "ISO-8859-1,utf-8;q=0.7,*;q=0.3",
            "Accept-Encoding": "none",
            "Accept-Language": "en-US,en;q=0.8",
            "Connection": "keep-alive",
        }
        self.URL: str = "https://hianime.to"
        self.ENCODING = "utf-8"
        self.SUBTITLE_LANG: str = "en"
        self.OTHER_LANGS: list[str] = [
            "ita",
            "jpn",
            "pol",
            "por",
            "ara",
            "chi",
            "cze",
            "dan",
            "dut",
            "fin",
            "fre",
            "ger",
            "gre",
            "heb",
            "hun",
            "ind",
            "kor",
            "nob",
            "pol",
            "rum",
            "rus",
            "tha",
            "vie",
            "swe",
            "spa",
            "tur",
            "ces",
            "bul",
            "zho",
            "nld",
            "fra",
            "deu",
            "ell",
            "hin",
            "hrv",
            "msa",
            "may",
            "ron",
            "slk",
            "slo",
            "ukr",
        ]
        self.DOWNLOAD_ATTEMPT_CAP: int = 45
        self.DOWNLOAD_REFRESH: tuple[int, int] = (15, 30)
        self.BAD_TITLE_CHARS: list[str] = [
            "-",
            ".",
            "/",
            "\\",
            "?",
            "%",
            "*",
            "<",
            ">",
            "|",
            '"',
            "[",
            "]",
            ":",
        ]
        self.TITLE_TRANS: dict[int, Any] = str.maketrans(
            "", "", "".join(self.BAD_TITLE_CHARS)
        )
        self._user_data_dir = None  # Add this line

    def run(self):
        # Brute-force download all One Piece episodes from ep=2142 to ep=143880
        anime_name = "One Piece"
        anime_folder = anime_name.lower().replace(' ', '-')
        output_dir = os.path.join(self.args.output_dir, anime_folder)
        os.makedirs(output_dir, exist_ok=True)
        self.args.output_dir = output_dir

        print(f"{Fore.LIGHTGREEN_EX}Starting brute-force download for {anime_name} episodes (ep=2142 to ep=143880)...")
        base_url = "https://hianime.to/watch/one-piece-100?ep="
        start_ep = 2142
        end_ep = 143880
        for ep_id in range(start_ep, end_ep + 1):
            url = f"{base_url}{ep_id}"
            out_name = f"{anime_name}_ep{ep_id}"
            print(f"{Fore.LIGHTCYAN_EX}Trying episode ep={ep_id}...", end=" ")
            try:
                # Check if the page exists (status 200)
                resp = requests.get(url, headers=self.HEADERS, timeout=10)
                if resp.status_code == 404:
                    print(f"{Fore.LIGHTRED_EX}404 Not Found, skipping.")
                    continue
                elif resp.status_code != 200:
                    print(f"{Fore.LIGHTRED_EX}HTTP {resp.status_code}, skipping.")
                    continue
                print(f"{Fore.LIGHTGREEN_EX}Found! Downloading...")
                self.yt_dlp_download(url, self.HEADERS, os.path.join(output_dir, out_name))
            except Exception as e:
                print(f"{Fore.LIGHTRED_EX}Error: {e}, skipping.")

    def download_streams(self, anime: Anime, episodes: list[dict[str, Any]]):
        print(f"{Fore.LIGHTCYAN_EX}Starting download for {len(episodes)} episodes...")
        for ep in episodes:
            url = ep.get("url")
            ep_num = ep.get("episode")
            if not url:
                print(f"{Fore.RED}No URL for episode {ep_num}")
                continue
            out_dir = self.args.output_dir
            out_name = f"{anime.name}_S{anime.season_number:02d}E{ep_num:02d}_{anime.download_type}"
            self.yt_dlp_download(url, self.HEADERS, os.path.join(out_dir, out_name))


            #     print(f"\n\nError while downloading {name}: \n\n{e}")

    @staticmethod
    def get_download_type():
        ans = (
            input(
                f"\n{Fore.LIGHTCYAN_EX}Both sub and dub episodes are available. Do you want to download sub or dub? (Enter 'sub' or 'dub'):{Fore.LIGHTYELLOW_EX} "
            )
            .strip()
            .lower()
        )
        if ans == "sub" or ans == "s":
            return "sub"
        elif ans == "dub" or ans == "d":
            return "dub"
        print(
            f"{Fore.LIGHTRED_EX}Invalid response, please respond with either 'sub' or 'dub'."
        )
        return HianimeExtractor.get_download_type()

    def configure_driver(self) -> None:
        import tempfile
        import random
        import string
        import subprocess
        # Kill all Chrome processes before starting a new driver
        try:
            subprocess.run(["pkill", "-f", "chrome"], check=False)
        except Exception:
            pass

        mobile_emulation: dict[str, str] = {"deviceName": "iPhone X"}
        options: webdriver.ChromeOptions = webdriver.ChromeOptions()
        # Clean up any previous temp user data dir
        if self._user_data_dir and os.path.exists(self._user_data_dir):
            shutil.rmtree(self._user_data_dir, ignore_errors=True)
        # Add a random suffix to the temp dir for uniqueness
        rand_suffix = ''.join(random.choices(string.ascii_letters + string.digits, k=8))
        self._user_data_dir = tempfile.mkdtemp(prefix=f"hianime_chrome_{rand_suffix}_")
        options.add_argument(f"--user-data-dir={self._user_data_dir}")
        options.add_experimental_option("mobileEmulation", mobile_emulation)
        options.add_argument("--disable-blink-features=AutomationControlled")
        options.add_argument("window-size=600,1000")

        options.add_experimental_option(
            "prefs",
            {
                "profile.default_content_setting_values.notifications": 2,  # Block notifications
                "profile.default_content_setting_values.popups": 2,  # Block pop-ups
                "profile.managed_default_content_settings.ads": 2,  # Block ads
            },
        )
        options.add_argument("--disable-features=PopupBlocking")
        options.add_argument("--no-sandbox")
        options.add_argument("--disable-notifications")
        options.add_argument("--disable-backgrounding-occluded-windows")
        options.add_argument("--disable-gpu")
        options.add_argument("--log-level=3")
        options.add_argument("--silent")
        options.add_experimental_option("excludeSwitches", ["enable-logging"])

        seleniumwire_options: dict[str, bool] = {
            "verify_ssl": False,
            "disable_encoding": True,
        }

        self.driver: webdriver.Chrome = webdriver.Chrome(
            options=options,
            seleniumwire_options=seleniumwire_options,
        )

        stealth(
            self.driver,
            languages=["en-US", "en"],
            vendor="Google Inc.",
            platform="Win32",
            webgl_vendor="Intel Inc.",
            renderer="Intel Iris OpenGL Engine",
            fix_hairline=True,
        )

        self.driver.implicitly_wait(10)

        self.driver.execute_script(
            """
                window.alert = function() {};
                window.confirm = function() { return true; };
                window.prompt = function() { return null; };
                window.open = function() {
                    console.log("Blocked a popup attempt.");
                    return null;
                };
            """
        )

    def get_server_options(self, download_type: str) -> list[WebElement]:
        WebDriverWait(self.driver, 10).until(
            EC.presence_of_element_located((By.ID, "servers-content"))
        )

        options = [
            _type.find_element(By.CLASS_NAME, "ps__-list").find_elements(
                By.TAG_NAME, "a"
            )
            for _type in self.driver.find_element(
                By.ID, "servers-content"
            ).find_elements(By.XPATH, "./div[contains(@class, 'ps_-block')]")
        ]

        return (
            options[0]
            if len(options) == 1 or (download_type == "sub" or download_type == "s")
            else options[1]
        )

    def find_server_button(self, anime: Anime) -> WebElement | None:
        options = self.get_server_options(anime.download_type)
        selection = None

        if self.args.server:
            for option in options:
                if option.text.lower().strip() == self.args.server.lower().strip():
                    selection = option.text

        if not selection:
            if self.args.server:
                print(
                    f"{Fore.LIGHTGREEN_EX}The server name you provided does not exist\n"
                )
            print(
                f"\n{Fore.LIGHTGREEN_EX}Select the server you want to download from: \n"
            )

            server_names = []
            for i, option in enumerate(options):
                server_names.append(option.text)
                print(f"{Fore.LIGHTRED_EX} {i + 1}: {Fore.LIGHTCYAN_EX}{option.text}")

            self.driver.requests.clear()
            self.driver.quit()
            # Clean up the temporary user data directory if it was created
            import shutil
            if hasattr(self, '_user_data_dir') and self._user_data_dir is not None and os.path.exists(self._user_data_dir):
                shutil.rmtree(self._user_data_dir, ignore_errors=True)

            selection = server_names[
                get_int_in_range(
                    f"\n{Fore.LIGHTCYAN_EX}Server:{Fore.LIGHTYELLOW_EX} ",
                    1,
                    len(options),
                )
                - 1
            ]
        else:
            self.driver.requests.clear()
            self.driver.quit()

        print(f"\n{Fore.LIGHTGREEN_EX}You chose: {Fore.LIGHTCYAN_EX}{selection}")

        self.driver.get(anime.url)

        options = self.get_server_options(anime.download_type)

        for option in options:
            if option.text == selection:
                return option

        print(f"{Fore.LIGHTRED_EX}No matching server button could be found")
        return None

    def get_episode_urls(
        self, page: str, start_episode: int, end_episode: int
    ) -> list[dict[str, Any]]:
        episodes: list[dict[str, Any]] = []
        soup = BeautifulSoup(page, "html.parser")

        links: list[Tag] = soup.find_all("a", attrs={"data-number": True})  # type: ignore

        for link in links:
            episode_number: int = int(str(link.get("data-number")))

    @staticmethod
    def look_for_variants(m3u8_url: str, m3u8_headers: dict[str, Any]) -> str:
        response = requests.get(m3u8_url, headers=m3u8_headers)
        lines = response.text.splitlines()
        url = None
        for line in lines:
            if line.strip().endswith(".m3u8") and "iframe" not in line:
                url = urljoin(m3u8_url, line.strip())
                break
        if not url:
            print("No valid video variant found in master.m3u8")
            return ""

        return url



