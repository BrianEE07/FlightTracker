import os, time
import argparse
import requests
from dotenv import load_dotenv
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC

load_dotenv()
LINE_NOTIFY_TOKEN = os.getenv("LINE_NOTIFY_TOKEN")
headers = {'Authorization':'Bearer ' + LINE_NOTIFY_TOKEN}

def parse_args():
    parser = argparse.ArgumentParser(description='Flight Tracker')
    parser.add_argument('--flight', type=str, required=True, help='flight url to track')
    parser.add_argument('--threshold', type=int, default=500, help='price threshold to check price change')
    parser.add_argument('--time', type=int, default=20, help='time interval to check price')
    parser.add_argument('--debug', action='store_true', help='enable debug mode, print messages instead of push notifications')
    return parser.parse_args()

def get_webdriver(browser='Chrome'):
    assert browser in ['Chrome', 'Firefox'], 'Invalid browser!'
    options = getattr(webdriver, f"{browser}Options")()
    options.add_argument('--headless')
    options.add_argument('--window-size=1920,1080')
    options.add_argument('--start-maximized')
    driver = getattr(webdriver, browser)(options=options)
    driver.maximize_window()
    return driver

def get_flight_data(driver):
    try:
        # get location of from and to
        from_to = WebDriverWait(driver, 10).until(EC.presence_of_all_elements_located((By.CSS_SELECTOR, 'div[class="Ftz1rf"]')))
        assert len(from_to) == 2, 'Cannot get flight data! Check provided flight url.'
        from_str = from_to[0].find_elements(By.CSS_SELECTOR, 'span')[0].get_attribute('textContent')
        try:
            from_str += ' ' + from_to[0].find_elements(By.CSS_SELECTOR, 'span')[1].get_attribute('textContent')
        except:
            pass
        to_str = from_to[1].find_elements(By.CSS_SELECTOR, 'span')[0].get_attribute('textContent')
        try:
            to_str += ' ' + from_to[1].find_elements(By.CSS_SELECTOR, 'span')[1].get_attribute('textContent')
        except:
            pass
        # get date
        date = WebDriverWait(driver, 10).until(EC.presence_of_all_elements_located((By.CSS_SELECTOR, 'input[class="TP4Lpb eoY5cb j0Ppje"]')))
        date_str = date[0].get_attribute('value')
        if date[1].get_attribute('value'):
            date_str += ' ~ ' + date[1].get_attribute('value')
        return {'date': date_str, 'from': from_str, 'to': to_str}
    except Exception as e:
        print(f"Error getting flight data: {e}")
        driver.close()
        driver.quit()
        exit()


def push_message(message, img=None):
    params = {"message": message}
    if img is not None:
        imageFile = {'imageFile' : img}
        r = requests.post("https://notify-api.line.me/api/notify", headers=headers, params=params, files=imageFile)
    else:
        r = requests.post("https://notify-api.line.me/api/notify", headers=headers, params=params)
    if r.status_code != 200:
        print('push notification failed, status code:', r.status_code)
        # check image rate limit
        img_remain = requests.get("https://notify-api.line.me/api/status", headers=headers).headers['X-RateLimit-ImageRemaining']
        if img_remain == '0':
            requests.post("https://notify-api.line.me/api/notify", headers=headers, params={"message": "達到每小時圖片上傳數量限制，請稍等!"})

def flight_tracker(args):
    driver = get_webdriver()

    THRESHOLD = args.threshold
    TIME = args.time
    DEBUG = args.debug

    url = args.flight
    driver.get(url)
    flight_data = get_flight_data(driver)

    date_from_to = f"{flight_data['date']}\n{flight_data['from']} ➡️ {flight_data['to']}"
    message = f"\n我要搶到機票 [通知]\n{date_from_to}\n開始追蹤!🛫"
    push_message(message) if not DEBUG else print(message)
    
    all_time_min_price = 1000000
    last_min_price = 1000000

    try:
        i = 0
        while True:
            driver.refresh()
            print(f"[Step {i}]")
            i += 1
            try:
                best_flights = WebDriverWait(driver, 10).until(EC.presence_of_element_located((By.CSS_SELECTOR, 'div[jsname="IWWDBc"]')))
                loc, size = best_flights.location, best_flights.size
                prices = WebDriverWait(best_flights, 10).until(EC.presence_of_all_elements_located((By.CSS_SELECTOR, 'span[aria-label*="新台幣"]')))
                # remove empty, convert to int
                prices = [price for price in prices if price.text]
                prices = [int(price.text[1:].replace(',', '')) for price in prices]
                # get the minimum price
                min_price = min(prices)
                if min_price < all_time_min_price:
                    all_time_min_price = min_price
                print(f'    prices: {prices} min price: {min_price} all-time min price: {all_time_min_price}')
                # check if price change
                diff = abs(min_price - last_min_price)
                if diff == 0:
                    print('    price not change')
                elif diff < THRESHOLD:
                    print('    price slightly change')
                else:
                    best_flights.screenshot('screenshot.png')
                    screenshot = open('screenshot.png', 'rb')
                    diff = diff if last_min_price != 1000000 else 0
                    if min_price < last_min_price:
                        print('    price drop!, push notification...')
                        message = f"😍😍😍\n我要搶到機票 [通知]\n{date_from_to}\n價格下降!🔻${diff}\n現價 ${min_price}\n歷史低價 ${all_time_min_price}\n去訂票 ➡️ {url}"
                    else:
                        print('    price increase!, push notification...')
                        message = f"😭😭😭\n我要搶到機票 [通知]\n{date_from_to}\n價格上升!🔺${diff}\n現價 ${min_price}\n歷史低價 ${all_time_min_price}\n去訂票 ➡️ {url}"
                    push_message(message, screenshot) if not DEBUG else print(message)
                last_min_price = min_price
            except Exception as e:
                print(f"Error getting price: {e}")
            time.sleep(TIME)
    except KeyboardInterrupt:
        message = f"\n我要搶到機票 [通知]\n{date_from_to}\n結束追蹤!🛬"
        push_message(message) if not DEBUG else print(message)
        driver.close()
        driver.quit()

if __name__ == '__main__':
    args = parse_args()
    flight_tracker(args=args)