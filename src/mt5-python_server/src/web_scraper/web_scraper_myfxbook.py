import time
from selenium import webdriver
from selenium.webdriver.common.by import By
from bs4 import BeautifulSoup
import pandas as pd
from utils.time_utils import format_datetime


def convert_impact_str_to_int(impact_str):
    """
    Convert the string impact to it's interger value
    """
    if impact_str == 'Low':
        return 1
    elif impact_str == 'Medium':
        return 2
    elif impact_str == 'High':
        return 3
    else:
        raise ValueError


def parse_calendar(html):
    """
    Parse the html to collect the data

    return: Pandas Dataframe
    """
    soup = BeautifulSoup(html, "html.parser")

    rows = soup.find_all('tr')
    headers = [th.text.strip() for th in rows[0].find_all("th")][:-1]
    headers[3] = 'Country'
    headers.pop(1)
    headers.pop(1)

    calendar_tips = soup.find_all(id="calendarTip0")
    countries = []
    for country in calendar_tips:
        countries.append(country.get('title'))

    data = []
    index = 0
    for row in rows[2:]:
        row_data = []
        for td in row.find_all("td")[:-1]:
            row_data.append(td.text.strip())
        row_data.pop(1)
        row_data.pop(1)
        row_data[0] = format_datetime(row_data[0])
        row_data[1] = countries[index]
        row_data[3] = convert_impact_str_to_int(row_data[3])

        data.append(row_data)
        index += 1

    df = pd.DataFrame(data, columns=headers)
    df.replace('', None, inplace=True)

    return df


class WebScraperMyfxbook:
    """WebCrawler for myfxbook"""

    def __init__(self, email, password, url):
        self.email = email
        self.password = password
        self.__url = url
        self.__economic_calendar_route = "forex-economic-calendar"

    def download_economic_calendar(self):
        """
        Download the economic calendar data from yesterday

        return: Pandas DataFrame
        """
        driver = webdriver.Chrome()
        driver.get(self.__url + self.__economic_calendar_route)

        driver.implicitly_wait(90)

        self.__navigate_myfxbook_economic_calendar(driver)

        time.sleep(5)

        table = driver.find_element(By.ID, 'economicCalendarTable')
        table_html = table.get_attribute("outerHTML")

        return parse_calendar(table_html)

    def __navigate_myfxbook_economic_calendar(self, driver):
        """
        Navigate the start-up ads
        """
        ad_modal = driver.find_element(By.CLASS_NAME, 'continue-text')
        skip_btn = ad_modal.find_element(By.TAG_NAME, 'a')
        skip_btn.click()

        self.__myfxbook_connexion(driver)

        allow_btn = driver.find_element(By.ID, 'allowWebNotification')
        allow_btn.click()

        yesterday_btn = driver.find_element(By.ID, 'calendarYesterdayBtn')
        yesterday_btn.click()

    def __myfxbook_connexion(self, driver):
        """
        Connect to myfxbook account
        """
        login_btn = driver.find_element(By.ID, 'login-btn')
        login_btn.click()

        email_textbox = driver.find_element(By.ID, 'loginEmail')
        email_textbox.send_keys(self.email)

        password_textbox = driver.find_element(By.ID, 'loginPassword')
        password_textbox.send_keys(self.password)

        login_btn = driver.find_element(By.ID, 'login-btn')
        login_btn.click()

if __name__ == "__main__":
    myfxbook = WebScraperMyfxbook(
        email="alchemistcapitalmanagement@gmail.com",
        password=">B3)V:v62VFt0Rt=,",
        url="https://www.myfxbook.com/"
    )

    data = myfxbook.download_economic_calendar()
    print(data)