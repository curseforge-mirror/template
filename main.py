import os
import sys
import time
import logging
import cloudscraper
from bs4 import BeautifulSoup as Soup

cf_mirror_addon_name = "Enter Addon Name Here For Local Testing"

handler = logging.StreamHandler(sys.stdout)

logging.basicConfig(
    level=logging.INFO,
    # format="%(asctime)s [%(levelname)s] %(msg)s",
    format="{asctime} [{levelname}] {message}",
    style="{",
    datefmt="%Y-%m-%d %H:%M:%S",
    handlers=[handler],
)

log = logging.getLogger()


class CFScraper:
    def __init__(self, addon_name):

        if addon_name == cf_mirror_addon_name:
            log.warning("WARNING: Default Addon Name Being Used")

        self.addon_name = addon_name
        self.curseforge_base = "https://www.curseforge.com"
        self.curseforge_wow_base = "/wow/addons"
        self.curseforge_addon_base = f"{self.curseforge_wow_base}/{self.addon_name}"
        self.curseforge_info_url = f"{self.curseforge_base}{self.curseforge_addon_base}"
        self.curseforge_download_base = f"{self.curseforge_addon_base}/files/"
        self.curseforge_download_full = f"{self.curseforge_base}{self.curseforge_download_base}"
        self.curseforge_cdn_url = "https://edge.forgecdn.net/files"

        self.gv_name_scheme_lookup = {
            "WoW Retail": "",
            "WoW Classic": "-classic",
            "WoW Burning Crusade Classic": "-bc",
            "WoW Wrath of the Lich King Classic": "-wrath",
        }

        self.__create_scraper()

    def __create_scraper(self):
        self.scraper = cloudscraper.create_scraper(
            browser={},  # RNG Browser Agents
            interpreter='nodejs'
        )

    def get_file_name(self, full_href):
        download_url = full_href.replace(self.curseforge_download_base, self.curseforge_download_full)
        response = self.scraper.get(download_url)
        soup = Soup(response.content, features="html.parser")

        filename_element_selector = "span[class='text-sm']"

        filename_element = soup.select(filename_element_selector)[0]

        return filename_element.text.replace(".zip", "")

    def get_download_mapping(self):
        response = self.scraper.get(self.curseforge_info_url)

        if response.status_code != 200:
            log.error(
                f"ERROR: {self.addon_name} failed at download on url"
                f" {self.curseforge_info_url} -- error code {response.status_code}"
            )
            return None

        soup = Soup(response.content, features="html.parser")

        download_element_selector = "div[class='cf-sidebar-inner'] > *"
        download_game_version_selector = "a"
        download_url_version_selector = "li > div > a[class='overflow-tip truncate']"

        download_element = soup.select(download_element_selector)

        curseforge_mapping = {
            "WoW Retail": None,
            "WoW Classic": None,
            "WoW Burning Crusade Classic": None,
            "WoW Wrath of the Lich King Classic": None,
        }

        log.info(f"Found {len(download_element)} elements...")

        for x in range(0, len(download_element), 2):
            curseforge_mapping[download_element[x].find(download_game_version_selector).contents[0].strip()] = {
                "url": download_element[x + 1]
                .select(download_url_version_selector)[0]
                .get_attribute_list("href")[0]
                .replace(self.curseforge_download_base, ""),
                "file_name": self.get_file_name(
                    download_element[x + 1].select(download_url_version_selector)[0].get_attribute_list("href")[0]
                ),
            }

        curseforge_mapping = {k: v for k, v in curseforge_mapping.items() if v}

        log.info(f"Found URLS for {len(curseforge_mapping)} different versions!")

        for gv, info in curseforge_mapping.items():
            unsplit_url = info["url"]
            if len(unsplit_url) == 7:
                curseforge_mapping[gv]["url_first"] = unsplit_url[:4]
                curseforge_mapping[gv]["url_second"] = unsplit_url[-3:]
            elif len(unsplit_url) == 6:
                curseforge_mapping[gv]["url_first"] = unsplit_url[:3]
                curseforge_mapping[gv]["url_second"] = unsplit_url[-3:]
            elif len(unsplit_url) == 5:
                curseforge_mapping[gv]["url_first"] = unsplit_url[:3]
                curseforge_mapping[gv]["url_second"] = unsplit_url[-2:]
            else:
                raise Exception("idk weird length on url number thing")

        return curseforge_mapping

    def download_files(self, mapping):
        for gv, info in mapping.items():
            url = f"{self.curseforge_cdn_url}/{info['url_first']}/{info['url_second']}/{info['file_name']}.zip"
            response = self.scraper.get(url, allow_redirects=True)
            if response.status_code != 200:
                log.error(
                    f"ERROR: {self.addon_name} v{gv} failed at download -- error code {response.status_code}"
                    f"\n -----\n{response.text}\n-----"
                )
                continue
            file_name = f"{info['file_name']}.zip"
            if not info["file_name"].endswith(self.gv_name_scheme_lookup[gv]):
                file_name = f"{info['file_name']}{self.gv_name_scheme_lookup[gv]}.zip"
            with open(file_name, "wb") as f:
                f.write(response.content)

    def run(self):
        log.info(f"Pulling files for addon: {self.addon_name}")

        count = 0
        while count < 10:
            mapping = self.get_download_mapping()
            if mapping:
                break
            log.warning("Didn't find mapping, retrying...")
            self.__create_scraper()
            time.sleep(count)
            count += 1

        if not mapping:
            raise Exception("No Downloads Found")
        log.info("Mapping Finalized! Downloading Files from CDN...")
        self.download_files(mapping)


if __name__ == "__main__":
    scraper = CFScraper(os.getenv("ADDON_NAME", cf_mirror_addon_name))
    scraper.run()
