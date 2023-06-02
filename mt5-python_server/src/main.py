from server import Server
from web_crawler_myfxbook import WebCrawlerMyfxbook


def main():
    """Main"""
    # Server(verbose=True)
    web = WebCrawlerMyfxbook(
        "alchemistcapitalmanagement@gmail.com",
        ">B3)V:v62V$Ft0Rt=,",
        "https://www.myfxbook.com/"
    )
    web.download_economic_calendar()


if __name__ == '__main__':
    main()
