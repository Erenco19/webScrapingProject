import requests
from bs4 import BeautifulSoup

# Initialize a session
session = requests.Session()

# Define common headers
headers = {
    "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
    "Accept-Language": "en-GB,en;q=0.9,az-AZ;q=0.8,az;q=0.7,en-US;q=0.6,tr;q=0.5",
    "Accept-Encoding": "gzip, deflate, br, zstd"
}


def handle_requests(initial_page_url, cookie):
    products_in_the_page = []

    # Step 1: Send GET request to the initial page
    response = session.get(initial_page_url, headers=headers)
    if response.status_code != 200:
        print(f"Initial page request failed with status code {response.status_code}")
        exit()

    # Step 3: Trigger show-product-flag request
    show_product_flag_url = "https://online.hafele.live/show-product-flag"
    show_product_flag_headers = {
        "User-Agent": headers["User-Agent"],
        "Accept": "*/*",
        "Referer": initial_page_url,
        "X-Requested-With": "XMLHttpRequest",
        "Cookie": cookie
    }
    response = session.get(show_product_flag_url, headers=show_product_flag_headers)
    if response.status_code != 200:
        print(f"Show-product-flag request failed with status code {response.status_code}")
        exit()

    # Step 4: Fetch the updated page content
    updated_page_url = initial_page_url
    response = session.get(updated_page_url, headers=headers)
    if response.status_code != 200:
        print(f"Updated page request failed with status code {response.status_code}")
        exit()

    # Parse the updated page content with BeautifulSoup
    soup = BeautifulSoup(response.content, "html.parser")

    # Find all elements with class 'product-link'
    product_links = soup.find_all("span", class_="product-link")

    # Check if there are any product links and print them
    if product_links:
        for product_link in product_links:
            product_url = "https://online.hafele.live/" + product_link.get("url", "N/A")
            product_code = product_link.get_text(strip=True)
            products_in_the_page.append((product_code, product_url))
        return products_in_the_page
    else:
        print("No product links found.")
