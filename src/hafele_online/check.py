import sqlite3
import handle_button_click
from urllib3.util import Retry
import requests
from requests.adapters import HTTPAdapter
from bs4 import BeautifulSoup as bs4
import pandas as pd


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

def read_excel(file_path):
    excel_data = pd.read_excel(file_path)
    data = pd.DataFrame(excel_data, columns=["product_id"])
    stock_code_list = list()
    for code in data.values:
        stock_code_list.append(str(code[0]))
    return stock_code_list

def create_category(conn, product_id, category_name, category_link):
    sql = '''INSERT INTO NotFoundProducts(product_id,category_name, category_link) VALUES(?,?,?)'''
    cur = conn.cursor()
    cur.execute(sql, (product_id, category_name, category_link,))
    conn.commit()
    return cur.lastrowid

def main():
    db_conn = sqlite3.connect('hafele_all_products.db')
    excel_file_path = "/Users/godfather/Desktop/products_to_be_pulled_hafele_online.xlsx"
    products_list = read_excel(excel_file_path)
    for product in products_list:
        product_url = f"https://online.hafele.live/product-p-{product}"
        try:
            product_soup = return_page_soup_with_retry(product_url)
            breadcrumb_section = product_soup.find("ul", id="breadcrumb-")
            li_list = breadcrumb_section.find_all("li")
            category_link = li_list[len(li_list)-2]
            category_name = category_link.text.strip()
            category_link_text = "https://online.hafele.live" + category_link.find("a").get("href")
            create_category(db_conn, product, category_name, category_link_text)
            print(f"{product}'s cat is {category_name}")
        except Exception as e:
            print(f"Error on {product}, {e}")

if __name__ == '__main__':
    main()