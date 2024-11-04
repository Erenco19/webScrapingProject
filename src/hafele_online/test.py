import hafele_online_get_products
import hafele_online_get_categories
import extract_product_info as epi
import time


def main():
    st = time.time()
    hafele_online_get_categories.main()
    hafele_online_get_products.main()
    epi.main()
    et = time.time()
    process_time =(et-st)/60
    print(f"Time took to get all the products in hafele online {process_time} minutes.")

if __name__ == "__main__":
    main()