import sqlite3
from datetime import date
import concurrent.futures
import requests
from bs4 import BeautifulSoup
import pandas as pd
import re
import os
from dotenv import load_dotenv
from functools import partial
import send_mail

# relevant configs for the error logging
import logging
logging.basicConfig(filename='/tmp/hafeleerrors.log', level=logging.DEBUG, format='%(asctime)s %(levelname)s %(message)s')
logger = logging.getLogger(__name__)

load_dotenv()

login_url = "https://online.hafele.live/login?logout=true"

payload = {
    "username": os.getenv("hafele_online_username"),
    "password": os.getenv("hafele_online_password")
}

headers = {
    "Referer": "https://online.hafele.live/login?logout=true",
    "Origin": "https://online.hafele.live",
    "Content-Type": "application/x-www-form-urlencoded",
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/16.3 Safari/605.1.15"
}


def read_excel(file_path):
    excel_data = pd.read_excel(file_path)
    data = pd.DataFrame(excel_data, columns=["stockCode"])
    stock_code_list = list()
    for code in data.values:
        stock_code_list.append(str(code[0]))
    return stock_code_list


def extract_integer(string):
    integers = re.findall(r'\d+', string)
    integers = [int(i) for i in integers]
    merged_string = ''.join(map(str, integers))
    return merged_string


def extract_string(string):
    # Use regular expressions to find and capture non-integer parts of the string
    non_integer_parts = re.findall(r'\D+', string)

    # Remove any empty strings from the result
    non_integer_parts = [part.strip() for part in non_integer_parts if part.strip()]

    non_integer_parts = ''.join(map(str, non_integer_parts))

    if "." in non_integer_parts:
        non_integer_parts = non_integer_parts.replace(".", "")

    return non_integer_parts


def extract_stock_info_from_page(product_soup):
    content_panels = product_soup.find_all("div", class_="content panel")
    for panel in content_panels:
        if panel.find("legend"):
            if "Stok" in panel.find("legend").text:
                find_tds = panel.find_all("td")
                package_quantity = extract_integer(find_tds[0].text)
                package_type = extract_string(find_tds[0].text)
                stock_quantity = extract_integer(find_tds[1].text)
                stock_type = extract_string(find_tds[1].text)

                return [package_quantity, package_type, stock_quantity, stock_type]


def extract_price_info(product_soup):
    find_spans = product_soup.find_all("span", class_="price price")[:3]
    product_price = list()
    for price in find_spans:
        first_price = price.text.replace(".", "")
        sec_price = first_price.replace(",", ".")
        final_price = sec_price.replace("TRY", "")
        product_price.append(final_price.strip())
    return product_price


def return_stock_variant(product_soup):
    price_div = product_soup.find("div", id="price")
    if price_div:
        stock_type_variant_div = price_div.find_all("div")[9]
        if stock_type_variant_div:
            return stock_type_variant_div.find("span").get_text()
        else:
            return "urun bilgisi bulunamadi"


def return_advantage_box(product_soup):
    advantage_box_div = product_soup.find("div", class_="advantage-box")
    if advantage_box_div:
        if "N//A" in str(advantage_box_div):
            return "fayda ve ozellikler tablosu bulunamadi"
        else:
            # do the proper manipulations to the div as string
            all_content = advantage_box_div.get_text()
            description = all_content.replace(r"#### Fayda ve Özellikler\n*", "").strip()
            proper_html = f'''<div id="advantage-box" class="advantage-box"><h4 id="fayda-ve-özellikler">Fayda ve Özellikler</h4>
            <ul>
            <li>{description}</li>
            </ul>
            </div>'''
            return proper_html
    else:
        return "fayda ve ozellikler tablosu bulunamadi"


def scrape_each_product(product_code, db_cursor = None):
    try:
        session = requests.session()
        login_response = session.post(
            login_url,
            headers=headers,
            data=payload
        )

        if login_response.status_code == 200:
            if "Kullancı Bilgileriniz Hatalıdır" not in login_response.text:
                content_url = f"https://online.hafele.live/product-p-{product_code}"
                content_response = session.get(content_url)

                if "Internal Server Error" not in content_response.text:
                    content_soup = BeautifulSoup(content_response.text, "html5lib")
                    product_stock_list = extract_stock_info_from_page(content_soup)
                    product_price_list = extract_price_info(content_soup)
                    stock_variant = return_stock_variant(content_soup)
                    advantage_box = return_advantage_box(content_soup)
                    row_list = [product_code, product_stock_list[0], product_stock_list[1], product_stock_list[2],
                                product_stock_list[3], product_price_list[0], product_price_list[1], product_price_list[2], stock_variant, str(advantage_box)]
                    print(f"{product_code} done.")
                else:
                    row_list = [product_code, "does not exist", "does not exist", "does not exist", "does not exist",
                                "does not exist", "does not exist", "does not exist", "does not exist", "does not exist"]
                    print(f"{product_code} does not exist on hafele online but done.")

                return row_list
    except Exception as e:
        logger.error(e)
        print(f"Error with the product id: {product_code}, {e}")


def main():
    # creating the database and the tables within it
    db_conn = sqlite3.connect('hafele_products.sqlite')
    cur = db_conn.cursor()

    # table to read the product ids
    cur.execute('''CREATE TABLE IF NOT EXISTS products_to_be_read
        (product_id STRING PRIMARY KEY)''')
    product_list = read_excel("products_to_be_read.xlsx")
    for product in product_list:
        cur.execute('INSERT OR IGNORE INTO products_to_be_read (product_id) VALUES ( ? )', (product,))

    # get the products to be scraped
    cur.execute('SELECT product_id FROM products_to_be_read ORDER BY product_id ASC')
    products = list()
    for product in cur:
        products.append(product[0])
        print(f"Product: {product}")

    # create today's date for the product_info_table
    today_s_date = str(date.today()).replace('-', '_')
    product_info_table_name = f"products_info_{today_s_date}"

    # creating the table including the products within their info
    execution_string = f'''CREATE TABLE IF NOT EXISTS {product_info_table_name}
            (product_id STRING PRIMARY KEY, package_quantity INTEGER, package_type STRING, stock_amount INTEGER, stock_type STRING, product_price STRING)'''
    cur.execute(execution_string)

    with concurrent.futures.ThreadPoolExecutor() as executor:
        try:
            data_to_be_extracted = executor.map(partial(scrape_each_product, db_cursor=cur), products)
        except Exception as e:
            print("An error occured, trying scraping again.", e)
            data_to_be_extracted = executor.map(partial(scrape_each_product, db_cursor=cur), products)
        finally:
            print("Not worked.")

    # get rid of none values
    filtered_data = filter(None, data_to_be_extracted)

    # convert filtered data to a list
    dataframe_extract = list(filtered_data)

    # create the dataframe
    hd = ["product_id", "package_quantity", "package_type", "stock_amount", "stock_type", "tavsiye_edilen_fiyat", "kontrol_liste_fiyat", "net_fiyat", "stok_urunu_tipi", "fayda_ve_ozellikler"]
    df = pd.DataFrame(dataframe_extract, columns=hd)

    #sending the mail process
    # deleting the excel file if exists
    try:
        with open("excel_file_to_mail.xlsx") as excel_file:
            os.remove("excel_file_to_mail.xlsx")
    except FileNotFoundError:
        pass
    # extract the dataframe
    df.to_excel("excel_file_to_mail.xlsx", sheet_name="Urunler")
    recipient_email = os.getenv("gmail_receiver_email")
    recipient_email_2 = os.getenv("gmail_receiver_email_2")
    recipient_email_3 = os.getenv("gmail_receiver_email_3")
    send_mail.send_mail_with_excel(recipient_email)
    send_mail.send_mail_with_excel(recipient_email_2)
    send_mail.send_mail_with_excel(recipient_email_3)
    print(f"The mails have been sent to {recipient_email}, {recipient_email_2} and {recipient_email_3}.")


    # filter the dataframe so that the non-existent items won't be extracted to the database
    dataframe_to_be_extracted_to_the_db = df.query('package_quantity != "does not exist"')
    # extract to the database
    for index, row in dataframe_to_be_extracted_to_the_db.iterrows():
        execution_script = f"INSERT OR IGNORE INTO {product_info_table_name} VALUES (?, ?, ?, ?, ?, ?)"
        data_tuple = (row['product_id'], row['package_quantity'], row['package_type'], row['stock_amount'], row['stock_type'], row['kontrol_liste_fiyat'])
        cur.execute(execution_script, data_tuple)

    db_conn.commit()
    db_conn.close()


if __name__ == "__main__":
    main()