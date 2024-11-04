import sqlite3
from sqlite3 import Error
import requests
from bs4 import BeautifulSoup as bs4
import os
from dotenv import load_dotenv
import handle_button_click
from requests.adapters import HTTPAdapter
from urllib3.util import Retry


def return_page_soup_with_retry(url, retries=3, backoff_factor=0.5):
    session = requests.Session()
    retry_strategy = Retry(
        total=retries,
        backoff_factor=backoff_factor,
        status_forcelist=[500, 502, 503, 504],
    )
    adapter = HTTPAdapter(max_retries=retry_strategy)
    session.mount("https://", adapter)
    session.mount("http://", adapter)

    try:
        response = session.get(url)
        if response.status_code == 200:
            return bs4(response.content, "html.parser")
        else:
            print(f"Error: Received status code {response.status_code} for URL: {url}")
            print(f"Response content: {response.content}")
            return None
    except Exception as e:
        print(f"An error occurred while fetching URL: {url}. Error: {e}")
        return None

load_dotenv()

headers = {
    "authority": "online.hafele.live",
    "method": "GET",
    "scheme": "https",
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,image/apng,*/*;q=0.8,application/signed-exchange;v=b3;q=0.7",
    "Accept-Encoding": "gzip, deflate, br, zstd",
    "Accept-Language": "en-GB,en;q=0.9,az-AZ;q=0.8,az;q=0.7,en-US;q=0.6,tr;q=0.5",
    "Cache-Control": "max-age=0",
    "Cookie": "JSESSIONID=A6D60CBAF825035AF5A51B6AF931ED8C",
    "Priority": "u=0, i",
    "Sec-Ch-Ua-Mobile": "?0",
    "Sec-Ch-Ua-Platform": "macOS",
    "Sec-Fetch-Dest": "document",
    "Sec-Fetch-Mode": "navigate",
    "Sec-Fetch-Site": "same-origin",
    "Sec-Fetch-User": "?1",
    "Upgrade-Insecure-Requests": "1",
    "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36"
}

payload = {
    "username": os.getenv("hafele_online_username"),
    "password": os.getenv("hafele_online_password")
}


def return_all_products_in_the_page(category_url):
    global products_in_the_page
    try:
        # Send the initial request to get the session ID
        initial_response = return_page_soup_with_retry(category_url)

        if initial_response:
            # Extract the session ID from the response headers
            session_id = initial_response.cookies.get('JSESSIONID') if initial_response.cookies else None

            # Check if the button element is present
            if initial_response.find("div", class_="mobileShow", onclick="showProduct();"):
                products_in_the_page = handle_button_click.handle_requests(category_url, cookie=session_id)
                print(f"The click button process is completed successfully.")
            else:
                # If button element is not present, extract products directly
                all_link_elements = initial_response.find_all("span", class_="product-link")
                products_in_the_page = []
                for product in all_link_elements:
                    product_link = "https://online.hafele.live" + product.get("url")
                    product_code = product.text
                    products_in_the_page.append((product_code, product_link))
        else:
            print(f"Error: Initial response is None for URL: {category_url}")
            products_in_the_page = []
    except Exception as e:
        print(f"An error occurred with the category: {category_url}. Error: {e}")
        # If there's an error, handle it and return an empty list
        products_in_the_page = []
    return products_in_the_page


def create_connection(db_file):
    """ create a database connection to the SQLite database specified by db_file """
    conn = None
    try:
        conn = sqlite3.connect(db_file)
        return conn
    except Error as e:
        print(e)
    return conn


def get_category_links(conn):
    all_categories = []
    cursor = conn.cursor()
    cursor.execute('''SELECT category_link FROM Categories''')
    result = cursor.fetchall()
    for link in result:
        all_categories.append(link[0])
    return all_categories


def save_product(conn, product_code, product_link, category_link):
    sql = ''' INSERT INTO Products(product_id, product_link, category_link)
                      VALUES(?,?,?) '''
    cur = conn.cursor()
    cur.execute(sql, (product_code, product_link, category_link))
    conn.commit()

    return cur.lastrowid


def delete_product_table(conn):
    sql = '''DELETE FROM Products'''
    cur = conn.cursor()
    cur.execute(sql)
    conn.commit()
    return cur.lastrowid


def main():
    conn = create_connection("hafele_all_products.db")

    # deleting the products table before starting to scrape
    delete_product_table(conn)

    all_category_links = get_category_links(conn)
    for category in all_category_links:
        try:
            products_within_category = return_all_products_in_the_page(category)
            products_within_category = list(dict.fromkeys(products_within_category))

            for product in products_within_category:
                save_product(conn, product[0], product[1], category)
            print(f"Category {category} done.")
        except Exception as e:
            print(f"Error occurred on the category {category}. Error: {e}")


if __name__ == "__main__":
    main()
