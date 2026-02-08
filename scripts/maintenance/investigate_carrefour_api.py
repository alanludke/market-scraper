"""
Investigate Carrefour network calls to discover API endpoints.
Uses Selenium with Chrome DevTools Protocol to capture network traffic.
"""

import json
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.chrome.options import Options
import time

def setup_driver():
    """Setup Chrome with network logging enabled."""
    chrome_options = Options()
    chrome_options.add_argument('--headless')
    chrome_options.add_argument('--disable-gpu')
    chrome_options.add_argument('--no-sandbox')
    chrome_options.add_argument('--disable-dev-shm-usage')

    # Enable Performance Logging
    chrome_options.set_capability('goog:loggingPrefs', {'performance': 'ALL'})

    driver = webdriver.Chrome(options=chrome_options)
    return driver

def extract_network_calls(driver):
    """Extract all network calls from browser logs."""
    logs = driver.get_log('performance')

    api_calls = []
    for entry in logs:
        try:
            log = json.loads(entry['message'])['message']

            # Look for network requests
            if log.get('method') == 'Network.requestWillBeSent':
                request = log['params']['request']
                url = request['url']

                # Filter API-related URLs
                if any(keyword in url.lower() for keyword in ['api', 'graphql', '_v', 'catalog', 'product']):
                    api_calls.append({
                        'url': url,
                        'method': request.get('method', 'GET'),
                        'headers': request.get('headers', {}),
                        'postData': request.get('postData', None)
                    })
        except:
            continue

    return api_calls

def main():
    print("🔍 Investigating Carrefour API endpoints...\n")

    driver = setup_driver()

    try:
        # Visit homepage
        print("1. Loading homepage...")
        driver.get('https://mercado.carrefour.com.br')
        time.sleep(5)

        # Visit a product page
        print("2. Loading product page...")
        driver.get('https://mercado.carrefour.com.br/agua-de-coco-natural-integral-kero-coco-sem-conservantes-garrafa-1l-4639405/p')
        time.sleep(5)

        # Try to trigger search
        print("3. Triggering search...")
        try:
            search_input = WebDriverWait(driver, 10).until(
                EC.presence_of_element_located((By.CSS_SELECTOR, 'input[type="search"], input[placeholder*="Busca"]'))
            )
            search_input.send_keys('arroz')
            time.sleep(3)
        except:
            print("   (Could not trigger search)")

        # Extract all API calls
        print("\n📡 Captured API calls:\n")
        api_calls = extract_network_calls(driver)

        # Deduplicate and organize by domain
        unique_urls = {}
        for call in api_calls:
            base_url = call['url'].split('?')[0]
            if base_url not in unique_urls:
                unique_urls[base_url] = call

        # Print organized results
        for url, call in sorted(unique_urls.items()):
            print(f"URL: {url}")
            print(f"  Method: {call['method']}")
            if call['postData']:
                print(f"  POST Data: {call['postData'][:200]}...")
            print()

        # Save detailed results
        with open('carrefour_api_calls.json', 'w', encoding='utf-8') as f:
            json.dump(list(unique_urls.values()), f, indent=2, ensure_ascii=False)

        print(f"\n✅ Found {len(unique_urls)} unique API endpoints")
        print(f"📄 Full details saved to: carrefour_api_calls.json")

    finally:
        driver.quit()

if __name__ == '__main__':
    main()
