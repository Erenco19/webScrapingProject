import re
import sqlite3
import requests
from bs4 import BeautifulSoup
import os
from dotenv import load_dotenv
from requests.adapters import HTTPAdapter
from urllib3.util import Retry

# HTML for table styling
table_style_css = '''
    .table-title{
        font-size: 2rem;
        font-weight: bold;
        }
        body {
            font-family: Arial, sans-serif;
            margin: 0;
            padding: 0;
        }
        table {
            width: 100%;
            border-collapse: collapse;
            margin: 20px 0;
            font-size: 18px;
            text-align: left;
        }
        th, td {
            padding: 12px;
            border: 1px solid #ddd;
        }
        th {
            background-color: #f4f4f4;
            text-align: center;
        }
        tr:nth-child(even) {
            box-shadow: 0 2px 8px rgba(0, 0, 0, 0.1);
        }
        tr:hover {
            background-color: #f1f1f1;
        }
        img.product-image {
            width: 100px;
            height: auto;
            border: 2px solid #007BFF;
            padding: 5px;
            border-radius: 5px;
        }
        a {
            text-decoration: none;
            color: inherit;
        }
        .product-link {
            color: #007BFF;
            font-weight: bold;
        }
        .product-link:hover {
            text-decoration: underline;
        }
        @media (max-width: 768px) {
            table, thead, tbody, th, td, tr {
                display: block;
            }
            thead tr {
                display: none;
            }
            tr {
                margin-bottom: 15px;
                box-shadow: 0 2px 8px rgba(0, 0, 0, 0.1);
            }
            td {
                text-align: right;
                padding-left: 50%;
                position: relative;
            }
            td::before {
                content: attr(data-label);
                position: absolute;
                left: 0;
                width: 50%;
                padding-left: 15px;
                font-weight: bold;
                text-align: left;
            }
        }'''

table_end_style = '''</body>
</html>'''

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


def remove_comments_from_table(table_html_str):
    remove_comments = re.sub(r'<!--.*?-->', '', str(table_html_str), flags=re.DOTALL)
    remove_script_tag = re.sub(r'<script*?</script>', '', str(remove_comments), flags=re.DOTALL)
    remove_li = re.sub(r'<li>*?</li>', '', str(remove_script_tag), flags=re.DOTALL)
    return remove_li


def return_product_soup(product_code, retries=3, backoff_factor=0.5):
    url = f"https://online.hafele.live/product-p-{str(product_code).strip()}"
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
            return BeautifulSoup(response.content, "html.parser")
        else:
            print(f"Error: Received status code {response.status_code} for URL: {url}")
            print(f"Response content: {response.content}")
            return None
    except Exception as e:
        print(f"An error occurred while fetching URL: {url}. Error: {e}")
        return None


def return_products_to_read(cur, limit):
    # get the products to be scraped
    cur.execute(f'SELECT product_id FROM Products ORDER BY product_id ASC LIMIT {limit}')
    products = list()
    for product in cur:
        products.append(product[0])
    return products


def style_table(table_soup_str, table_title, table_title_secondary):
    table_soup = BeautifulSoup(table_soup_str, 'html.parser')

    # Create the title tags
    title_tag = table_soup.new_tag('h2')
    title_tag.string = table_title
    second_title_tag = table_soup.new_tag('h3')
    second_title_tag.string = table_title_secondary

    # Insert the title tags
    table_soup.insert(0, title_tag)
    table_soup.insert(1, second_title_tag)

    # remove columns and style the table
    table_soup = remove_columns(table_soup)
    style_tag = table_soup.new_tag('style')
    style_tag.string = table_style_css
    table_soup.insert(0, style_tag)
    return table_soup.prettify()


def remove_columns(table_soup):
    # Iterate over the rows in the table body and header
    for row in table_soup.find_all(['tr']):
        # Find all cells in the row
        cells = row.find_all(['th', 'td'])
        # Remove the last three cells
        del cells[-3:]
        # remove the first column
        del cells[:1]
        # Clear the row's contents and re-add the modified cells
        row.clear()
        row.extend(cells)

    return BeautifulSoup(table_soup.prettify(), 'html.parser')


def fix_the_links(table_html):
    table_soup = BeautifulSoup(table_html, 'html.parser')
    tbody = table_soup.find("tbody")
    for row in tbody.find_all("tr"):
        td = row.find_all("td")[0]
        span = td.find("span")
        product_code = span.text.strip()
        product_link = f"https://www.evan.com.tr/arama/{product_code}"
        td.find("a")["href"] = product_link
        td.find("a")["target"] = "_blank"
        span["url"] = product_link
    return table_soup


def get_table_title(product_soup, table_id):
    all_rows = product_soup.find_all("div", class_="row")
    first_title = ""
    second_title = ""
    for div in all_rows:
        try:
            if div.find("table", id=table_id):
                first_title = div.find("legend").text.strip()
                second_title = div.find("h3").text.strip()
        except:
            continue
    return first_title, second_title


def finalize_process(product_soup):
    set_content_table_html = product_soup.find("table", id="productTableBoxBom")
    if set_content_table_html:
        set_content_table_html["style"] = ""
        # remove the comments
        set_content_table_html_stripped = remove_comments_from_table(set_content_table_html)
        # style the table
        get_titles = get_table_title(product_soup, "productTableBoxBom")
        set_content_styled_table = style_table(set_content_table_html_stripped, get_titles[0], get_titles[1])
        # give internal links to the table
        set_content_styled_table = fix_the_links(set_content_styled_table)
    else:
        set_content_styled_table = " "
    additional_products_table = product_soup.find("table", id="productTableView_Id0")
    if additional_products_table:
        additional_products_table["style"] = ""
        # remove the comments
        additional_products_table_html_stripped = remove_comments_from_table(additional_products_table)
        # style the table
        get_titles = get_table_title(product_soup, "productTableView_Id0")
        additional_content_styled_table = style_table(additional_products_table_html_stripped, get_titles[0],
                                                      get_titles[1])
        # give internal links to the table
        additional_content_styled_table = fix_the_links(additional_content_styled_table)
    else:
        additional_content_styled_table = " "
    if str(set_content_styled_table) + str(additional_content_styled_table) == "  ":
        return "tablo bulunamadi"
    else:
        return str(set_content_styled_table) + str(additional_content_styled_table)


def main():
    db_conn = sqlite3.connect('hafele_all_products.db')
    cur = db_conn.cursor()
    test_product = "001.35.040"
    table_html = return_product_soup(test_product)

    print(finalize_process(table_html))


if __name__ == "__main__":
    main()
