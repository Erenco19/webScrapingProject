import requests
from bs4 import BeautifulSoup
import re
import os
from dotenv import load_dotenv

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
    product_code = "911.02.894"
    print(scrape_each_product(product_code))

if __name__ == '__main__':
    main()