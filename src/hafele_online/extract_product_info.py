import sqlite3
import concurrent.futures
import requests
from bs4 import BeautifulSoup, Comment
import pandas as pd
import re
import os
from dotenv import load_dotenv
from functools import partial
import send_mail
import create_additional_table

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


def extract_product_table(product_soup):
    table = product_soup.find("table", class_="rtable table table-bordered mergeTable")
    first_div = r'''<div class="content panel">'''
    end_div = r'''</div>'''
    title = r'''<h4>Ürün Özellikleri</h4>'''
    table['style'] = r'''border: 1px solid #ddd; width: 100%; border-collapse: collapse; margin-top: 10px;'''
    rows = table.find_all("tr")
    for row in rows:
        th = row.find("th")
        th['style'] = r'''text-align: left; line-height: 1.2rem; padding: 8px; background-color: #f2f2f2; border: 1px solid #ddd;'''
        td = row.find("td")
        td['style'] = r'''line-height: 1.2rem; padding: 8px; border: 1px solid #ddd;'''
    if len(table) != 0:
        return str(first_div) + str(title) + str(table) + str(end_div)
    else:
        return "tablo bulunamadi"


def extract_product_title(product_soup):
    return product_soup.find("h1").text.strip()


def scrape_each_product(product_code):
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
                    content_soup = BeautifulSoup(content_response.text, "html.parser")
                    product_stock_list = extract_stock_info_from_page(content_soup)
                    product_price_list = extract_price_info(content_soup)
                    product_name = extract_product_title(content_soup)
                    product_description = extract_product_table(content_soup)
                    additional_products = create_additional_table.finalize_process(content_soup)
                    row_list = [product_code, product_name, product_stock_list[0], product_stock_list[1],
                                product_stock_list[2],
                                product_stock_list[3], product_price_list[0], product_price_list[1],
                                product_price_list[2], product_description,additional_products]
                    print(f"{product_code} done.")
                else:
                    row_list = [product_code, "does not exist", "does not exist", "does not exist", "does not exist",
                                "does not exist",
                                "does not exist", "does not exist", "does not exist", "does not exist",
                                "does not exist"]
                    print(f"{product_code} does not exist on hafele online but done.")
                return row_list
    except Exception as e:
        print(f"Product code: {product_code} An error occurred. {e}")


def return_products(cur):
    # delete the products that do not have a product_id
    delete_empty_products(cur)

    # get the products to be scraped
    cur.execute('SELECT product_id FROM Products ORDER BY product_id ASC')
    products = list()
    for product in cur:
        products.append(product[0])
    return products

def delete_empty_products(cur):
    cur.execute('delete from Products where product_id = ""')


def delete_products_detail_table(cur):
    cur.execute('delete from ProductsDetail')


def main():
    db_conn = sqlite3.connect('hafele_all_products.db')
    cur = db_conn.cursor()

    products = return_products(cur)

    # deleting the ProductsDetail table
    delete_products_detail_table(cur)

    with concurrent.futures.ThreadPoolExecutor() as executor:
        try:
            data_to_be_extracted = executor.map(partial(scrape_each_product), products)
        except Exception as e:
            print("An error occured, trying scraping again.", e)
            data_to_be_extracted = executor.map(partial(scrape_each_product), products)
        finally:
            print("Not worked.")

    # get rid of none values
    filtered_data = filter(None, data_to_be_extracted)

    # convert filtered data to a list
    dataframe_extract = list(filtered_data)

    # create the dataframe
    hd = ["urun_kodu", "urun_ismi", "paket_miktari", "paket_tipi", "stok_miktari", "stok_tipi", "tavsiye_edilen_fiyat",
          "kontrol_liste_fiyat", "net_fiyat", "urun_aciklamasi", "tamamlayici_urunler"]
    df = pd.DataFrame(dataframe_extract, columns=hd)

    # deleting the excel file if exists
    try:
        with open("hafeledeki_tum_urunler.xlsx") as excel_file:
            os.remove("hafeledeki_tum_urunler.xlsx")
    except FileNotFoundError:
        pass
    # extract the dataframe
    df.to_excel("hafeledeki_tum_urunler.xlsx", sheet_name="Urunler")

    # sending the mail process
    recipient_email = os.getenv("gmail_receiver_email")
    recipient_email_2 = os.getenv("gmail_receiver_email_2")
    recipient_email_3 = os.getenv("gmail_receiver_email_3")
    send_mail.send_mail_with_excel(recipient_email)
    send_mail.send_mail_with_excel(recipient_email_2)
    send_mail.send_mail_with_excel(recipient_email_3)
    print(f"The mails have been sent to {recipient_email}, {recipient_email_2} and {recipient_email_3}.")

    # filter the dataframe so that the non-existent items won't be extracted to the database
    dataframe_to_be_extracted_to_the_db = df.query('paket_miktari != "does not exist"')
    # extract to the database
    for index, row in dataframe_to_be_extracted_to_the_db.iterrows():
        execution_script = f"INSERT OR IGNORE INTO ProductsDetail VALUES (?, ?, ?, ?, ?, ?, ?)"
        data_tuple = (
            row['urun_kodu'], row['urun_ismi'], row['paket_miktari'], row['paket_tipi'], row['stok_miktari'], row['stok_tipi'],
            row['kontrol_liste_fiyat'])
        cur.execute(execution_script, data_tuple)

    db_conn.commit()
    db_conn.close()


if __name__ == "__main__":
    main()
