"""
Web scraper for forexlive.com
Enhanced with AI-assisted extraction for resilience
"""

import time
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.chrome.service import Service
from bs4 import BeautifulSoup
from utils.time_utils import print_with_datetime

# Try to import AI scraper (optional)
try:
    from infrastructure.scraping.ai_scraper import LLMScraper

    AI_SCRAPER_AVAILABLE = True
except ImportError:
    AI_SCRAPER_AVAILABLE = False
    LLMScraper = None


class WebScraperForexLive:
    """
    Web scraper for forexlive.com
    https://www.forexlive.com/
    """

    def __init__(self, url, driverpath, use_ai_scraper: bool = False):
        self.__url = url
        service = Service(executable_path=driverpath)
        options = webdriver.ChromeOptions()
        options.add_argument("--headless=new")
        self.__driver = webdriver.Chrome(service=service, options=options)
        self.__driver.implicitly_wait(90)
        self.__last_news_link = ""

        # Initialize AI scraper if available and requested
        self.__ai_scraper = None
        if use_ai_scraper and AI_SCRAPER_AVAILABLE:
            try:
                self.__ai_scraper = LLMScraper(provider="openai")
                print_with_datetime("AI scraper enabled for forexlive.com")
            except Exception as e:
                print_with_datetime(f"Could not initialize AI scraper: {e}")

        self.__start()

    def __start(self):
        """
        Start the web scraper
        """
        self.__driver.get(self.__url)

        while True:
            news_list = self.__driver.find_elements(
                By.CLASS_NAME, "article-list__item-wrapper"
            )

            links = [
                slot[0]
                .find_element(By.CLASS_NAME, "article-slot__title > a")
                .get_attribute("href")
                for slot in [
                    news.find_elements(By.CLASS_NAME, "article-slot__wrapper")
                    for news in news_list
                ]
            ]

            if self.__last_news_link == "":
                self.__last_news_link = links[-1]

            if links[0] != self.__last_news_link:
                links = links[: links.index(self.__last_news_link)]
                links.reverse()

                for link in links:
                    print(link)
                    self.__last_news_link = link
                    self.__parse_article(link)
                    print(f"Last news link: {self.__last_news_link}\n")
                self.__driver.get(self.__url)
            else:
                print_with_datetime("No new articles\n")
            time.sleep(60 * 5)

    def __parse_article(self, link):
        """
        Parse an article from forexlive.com
        Enhanced with AI-assisted extraction as fallback
        :param link: Article link
        :return: [category, tag, title, date, brief, text]
        """
        self.__driver.get(link)
        time.sleep(5)

        html = self.__driver.page_source
        soup = BeautifulSoup(html, "html.parser")

        # Try rule-based extraction first
        try:
            category = soup.find(
                "a", class_="article-header__category-section"
            ).text.strip()
            tag = soup.find("span", class_="tag__name").text.strip()
            title = soup.find("h1", class_="article__title").text.strip()
            date = soup.find("div", class_="publisher-details__date").text.strip()
            brief = soup.find("div", class_="article__wrapper").get("brief").strip()
            texts = soup.find("article", class_="article-body").find_all(
                ["h1", "p", "li"]
            )
            text = " ".join(
                [
                    (
                        t.text.strip()
                        if t.text.strip()[-1] == "."
                        else t.text.strip() + "."
                    )
                    for t in texts
                ]
            )

            print(f"Category: {category}")
            print(f"Tag: {tag}")
            print(f"Title: {title}")
            print(f"Date: {date}")
            print(f"Brief: {brief}")
            print(f"Text: {text}")

            return category, tag, title, date, brief, text

        except (AttributeError, KeyError) as e:
            # Rule-based extraction failed, try AI-assisted extraction
            if self.__ai_scraper:
                print_with_datetime(
                    f"Rule-based extraction failed, using AI scraper: {e}"
                )
                try:
                    extracted = self.__ai_scraper.extract(html, link)
                    # Map AI extraction to expected format
                    category = extracted.get("category", "unknown")
                    tag = extracted.get("tag", "")
                    title = extracted.get("title", "")
                    date = extracted.get("timestamp", "")
                    brief = extracted.get("summary", extracted.get("content", ""))[:200]
                    text = extracted.get("content", "")

                    return category, tag, title, date, brief, text
                except Exception as ai_error:
                    print_with_datetime(f"AI extraction also failed: {ai_error}")
                    # Return minimal data
                    return "unknown", "", "Failed to extract", "", "", ""
            else:
                print_with_datetime(
                    f"Extraction failed and AI scraper not available: {e}"
                )
                raise


if __name__ == "__main__":
    _url = "https://www.forexlive.com"
    _driverpath = "../../../drivers/chromedriver.exe"
    WebScraperForexLive(_url, _driverpath)
