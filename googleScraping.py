import time
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.common.keys import Keys
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
import pandas as pd
import re
import requests
import os
from bs4 import BeautifulSoup

# Configuration du driver Selenium
def setup_driver():
    chrome_options = Options()
    chrome_options.add_argument("--disable-blink-features=AutomationControlled")
    chrome_options.add_argument("--start-maximized")
    chrome_options.add_argument("--disable-gpu")
    chrome_options.add_argument("--no-sandbox")
    chrome_options.add_argument("--disable-dev-shm-usage")
    chrome_options.add_argument("--lang=en")
    return webdriver.Chrome(service=Service("/usr/local/bin/chromedriver"), options=chrome_options)

# Nettoyage des données
def clean_data(data):
    cleaned_data = []
    seen_urls = set() 

    for entry in data:
        # Vérifier la duplication des URL
        if entry['GMAP'] in seen_urls:
            continue
        seen_urls.add(entry['GMAP'])

        # Filtrer les champs vides
        if not entry['Name of business'] or not entry['Address'] or not entry['Phone']:
            continue

        # Vérifier si l'adresse contient des symboles bizarres comme ""
        """ if "" in entry['Address']:
            continue """

        cleaned_data.append(entry)

    return cleaned_data

# Extraction d'un email à partir d'une URL
def extract_email_from_website(url):
    try:
        headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/117.0.0.0 Safari/537.36",
            "Accept-Language": "en-US,en;q=0.9",
        }
        response = requests.get(url, headers=headers, timeout=30)
        response.raise_for_status()
        email_pattern = r'[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}'
        emails = re.findall(email_pattern, response.text)
        return emails[0] if emails else "Not available"
    except Exception as e:
        print(f"Erreur lors de l'extraction de l'email depuis {url}: {e}")
        return "Not available"

# Extraction des liens sociaux
def extract_social_link(url):
    try:
        headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/117.0.0.0 Safari/537.36",
            "Accept-Language": "en-US,en;q=0.9",
        }
        response = requests.get(url, headers=headers, timeout=30)
        response.raise_for_status()
        soup = BeautifulSoup(response.text, 'html.parser')
        social_links = [link['href'] for link in soup.find_all('a', href=True) if "facebook.com" in link['href']]
        return social_links if social_links else "Not available"
    except Exception as e:
        print(f"Erreur lors de l'extraction des réseaux sociaux depuis {url}: {e}")
        return "Not available"

# Défilement et chargement des résultats
def scroll_and_load_results(driver, max_scroll_attempts=30):
    scroll_attempts = 0

    while scroll_attempts < max_scroll_attempts:
        driver.execute_script("window.scrollBy(0, 1000);")
        time.sleep(2)

        # Vérifier l'état de la page
        ready_state = driver.execute_script("return document.readyState")
        if ready_state == "complete":
            scroll_attempts += 1
        else:
            scroll_attempts = 0 

    print(f"Défilement terminé après {scroll_attempts} tentatives.")

# Scraping des résultats Google Maps
def scrape_google_maps(sector, location_name, max_results=12):
    driver = setup_driver()
    driver.get("https://www.google.com/maps?hl=en")
    time.sleep(3)

    # Accepter la politique de confidentialité
    try:
        privacy_button = WebDriverWait(driver, 10).until(
            EC.element_to_be_clickable((By.XPATH, "//button[normalize-space()='Accept all']"))
        )
        privacy_button.click()
    except Exception as e:
        print(f"Erreur lors de l'acceptation de la politique de confidentialité : {e}")

    # Recherche de l'entreprise
    search_box = WebDriverWait(driver, 10).until(EC.presence_of_element_located((By.ID, "searchboxinput")))
    search_box.send_keys(f"{sector} in {location_name}")
    search_box.send_keys(Keys.RETURN)
    time.sleep(2)

    business_data = []
    results_scraped = 0
    visited_urls = set()

    while results_scraped < max_results:
    
        scroll_and_load_results(driver)
        results = driver.find_elements(By.CLASS_NAME, "Nv2PK")
        for result in results:
            if results_scraped >= max_results:
                break

            try:
                result.click()
                time.sleep(2)

                name = driver.find_element(By.CLASS_NAME, "DUwDvf").text if driver.find_elements(By.CLASS_NAME, "DUwDvf") else "Not available"
                address = driver.find_element(By.XPATH, "//button[contains(@data-item-id, 'address')]").text if driver.find_elements(By.XPATH, "//button[contains(@data-item-id, 'address')]") else "Not available"
                phone = driver.find_element(By.XPATH, "//button[contains(@data-item-id, 'phone')]").text if driver.find_elements(By.XPATH, "//button[contains(@data-item-id, 'phone')]") else "Not available"
                website_element = driver.find_element(By.XPATH, "//a[contains(@data-item-id, 'authority')]")
                website = website_element.get_attribute("href") if website_element else "Not available"
                emails = extract_email_from_website(website) if website != "Not available" else "Not available"
                social = extract_social_link(website) if website != "Not available" else "Not available"
                rating = driver.find_element(By.CLASS_NAME, "fontDisplayLarge").text if driver.find_elements(By.CLASS_NAME, "fontDisplayLarge") else "Not available"
                gmap_url = driver.current_url

                if gmap_url in visited_urls:
                    continue
                visited_urls.add(gmap_url)

                business_data.append({
                    "Name of business": name,
                    "Address": address,
                    "Phone": phone,
                    "Facebook": social,
                    "Email": emails,
                    "Website": website,
                    "GMAP": gmap_url,
                    "Rating": rating
                })
                results_scraped += 1

            except Exception as e:
                print(f"Erreur lors de l'extraction d'un résultat : {e}")
                continue

    driver.quit()
    return business_data

# Sauvegarde dans un fichier Excel
def save_cleaned_data_to_excel(all_data):
    cleaned_data = clean_data(all_data)
    folder_name = "Scraped_data_Final"
    if not os.path.exists(folder_name):
        os.makedirs(folder_name)

    file_name = os.path.join(folder_name, "London_Data_Generation.xlsx")
    pd.DataFrame(cleaned_data).to_excel(file_name, index=False)
    print(f"Données nettoyées enregistrées dans {file_name}")

# Exemple d'utilisation
if __name__ == "__main__":
    sectors = ["General Contractor"]
    locations = ["London, England"]
    all_data = []

    for location in locations:
        for sector in sectors:
            print(f"Scraping {sector} in {location}...")
            data = scrape_google_maps(sector, location, max_results=12)
            all_data.extend(data)

    save_cleaned_data_to_excel(all_data)
