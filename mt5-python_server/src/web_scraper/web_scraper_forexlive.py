"""
Web scraper for forexlive.com
"""
import time
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.chrome.service import Service
from bs4 import BeautifulSoup
from utils.time_utils import print_with_datetime


class WebScraperForexLive:
    """
    Web scraper for forexlive.com
    https://www.forexlive.com/
    """
    def __init__(self, url, driverpath):
        self.__url = url
        service = Service(executable_path=driverpath)
        options = webdriver.ChromeOptions()
        options.add_argument('--headless=new')
        self.__driver = webdriver.Chrome(service=service, options=options)
        self.__driver.implicitly_wait(90)
        self.__last_news_link = ""

        self.__start()

    def __start(self):
        """
        Start the web scraper
        """
        self.__driver.get(self.__url)

        while True:
            news_list = self.__driver.find_elements(By.CLASS_NAME, 'article-list__item-wrapper')

            links = [slot[0].find_element(By.CLASS_NAME, 'article-slot__title > a').get_attribute('href')
                     for slot in [news.find_elements(By.CLASS_NAME, 'article-slot__wrapper') for news in news_list]]

            if self.__last_news_link == '':
                self.__last_news_link = links[-1]

            if links[0] != self.__last_news_link:
                links = links[:links.index(self.__last_news_link)]
                links.reverse()

                for link in links:
                    print(link)
                    self.__last_news_link = link
                    self.__parse_article(link)
                    print(f'Last news link: {self.__last_news_link}\n')
                self.__driver.get(self.__url)
            else:
                print_with_datetime('No new articles\n')
            time.sleep(60 * 5)

    def __parse_article(self, link):
        """
        Parse an article from forexlive.com
        :param link: Article link
        :return: [category, tag, title, date, brief, text]
        """
        self.__driver.get(link)
        time.sleep(5)

        soup = BeautifulSoup(self.__driver.page_source, 'html.parser')

        category = soup.find('a', class_='article-header__category-section').text.strip()
        print(f'Category: {category}')
        tag = soup.find('span', class_='tag__name').text.strip()
        print(f'Tag: {tag}')
        title = soup.find('h1', class_='article__title').text.strip()
        print(f'Title: {title}')
        date = soup.find('div', class_='publisher-details__date').text.strip()
        print(f'Date: {date}')
        brief = soup.find('div', class_='article__wrapper').get('brief').strip()
        print(f'Brief: {brief}')
        texts = soup.find('article', class_='article-body').find_all(['h1', 'p', 'li'])
        text = " ".join([t.text.strip() if t.text.strip()[-1] == '.' else t.text.strip() + '.' for t in texts])
        print(f'Text: {text}')

        return category, tag, title, date, brief, text

if __name__ == '__main__':
    _url = 'https://www.forexlive.com'
    _driverpath = '../../../drivers/chromedriver.exe'
    WebScraperForexLive(_url, _driverpath)
