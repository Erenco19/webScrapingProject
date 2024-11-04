import sqlite3
from sqlite3 import Error
import requests
from bs4 import BeautifulSoup as bs4
import concurrent.futures
from functools import partial


# db part
def create_connection(db_file):
    """ create a database connection to the SQLite database specified by db_file """
    conn = None
    try:
        conn = sqlite3.connect(db_file)
        return conn
    except Error as e:
        print(e)
    return conn


def create_table(conn, create_table_sql):
    """ create a table from the create_table_sql statement """
    try:
        c = conn.cursor()
        c.execute(create_table_sql)
    except Error as e:
        print(e)


def create_product(conn, product_code):
    sql = ''' INSERT INTO Products(product_id, product_link) VALUES(?,?) '''
    cur = conn.cursor()
    product_link = f"https://online.hafele.live/product-p-{product_code}"
    cur.execute(sql, (product_code, product_link,))
    conn.commit()
    return cur.lastrowid


def delete_category_table(conn):
    sql = '''DELETE FROM Categories'''
    cur = conn.cursor()
    cur.execute(sql)
    conn.commit()
    return cur.lastrowid


def create_category(conn, category_link, is_deepest):
    sql = '''INSERT INTO Categories(category_link,is_deepest_sub_category) VALUES(?,?)'''
    cur = conn.cursor()
    cur.execute(sql, (category_link, is_deepest,))
    conn.commit()
    return cur.lastrowid


def return_page_soup(url):
    """ sending a request to the web page and extracting the soup object """
    session = requests.session()
    response = session.get(url)
    if response.status_code == 200:
        page_soup = bs4(response.text, "html.parser")
        session.close()
        return page_soup
    else:
        return "404"


def return_categories(page_soup):
    all_categories = []
    try:
        categories = page_soup.find_all("div", class_="category-cover__details")
        for category in categories:
            category_name = category.find("a").text
            category_link = "https://online.hafele.live" + category.find("a").get("href")
            all_categories.append((category_name, category_link))
        return all_categories
    except AttributeError:
        print(f"{page_soup} has no attribute 'find_all'")


def has_sub_category(link):
    link_soup = return_page_soup(link)
    try:
        categories = link_soup.find_all("div", class_="category-cover__details")
        if categories == []:
            return False
        else:
            return True
    except AttributeError:
        print(f"{link_soup} object do not have the attribute find_all")


def get_all_the_links(main_url):
    visited_links = set()  # Keep track of visited links to avoid revisiting
    links_to_visit = [(main_url,)]  # Start with the main URL
    all_category_links = []
    while links_to_visit:
        current_link = links_to_visit.pop(0)  # Get the first link in the queue
        if current_link[0] not in visited_links:
            visited_links.add(current_link[0])  # Mark the link as visited
            current_soup = return_page_soup(current_link[0])
            categories = return_categories(current_soup)

            for category in categories:
                category_name, category_link = category
                if has_sub_category(category_link):
                    links_to_visit.append((category_link,))  # Add subcategory link to the queue
                else:
                    print(category_link)
                    all_category_links.append(category_link)
    print("All links without subcategories visited.")
    return all_category_links


def main():
    conn = create_connection("hafele_all_products.db")
    main_url = "https://online.hafele.live/ana-sayfa-c-10001"
    all_category_links = get_all_the_links(main_url)

    # deleting the categories table
    delete_category_table(conn)

    # remove the main url from the link list
    if "https://online.hafele.live/ana-sayfa-c-10001" in all_category_links:
        all_category_links.remove("https://online.hafele.live/ana-sayfa-c-10001")

    # remove duplicates if any from the list of links to be written into the db
    all_category_links = list(dict.fromkeys(all_category_links))
    # removing the main page of the website as it is irrelevant
    # re-write the whole categories table
    print(f"Length of all the category links: {len(all_category_links)}")
    print("The links are being saved to the database now.")
    for link in all_category_links:
        is_deepest = "true " if has_sub_category(link) is False else "false"
        create_category(conn, link, is_deepest)

    print("All the links are saved to the database.")


if __name__ == "__main__":
    main()
