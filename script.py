import requests
from bs4 import BeautifulSoup
from datetime import datetime, timedelta

# --- Configuration ---
BASE_URL = "https://kafeterya.metu.edu.tr/"
CALENDAR_URL_TEMPLATE = BASE_URL + "?date_filter[value][date]={date}"
LUNCH_TIME = "11:40 to 12:30 GMT+3"
DINNER_TIME = "17:40 to 18:30 GMT+3"

def fetch_and_format_menu(date_str: str) -> dict or None:
    """
    Fetches the menu for a given date (DD/MM/YYYY) and formats the data 
    for calendar events using robust parsing. Returns None if no valid menu is found.
    """
    url = CALENDAR_URL_TEMPLATE.format(date=date_str)
    
    try:
        headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'
        }
        response = requests.get(url, headers=headers, timeout=10)
        response.raise_for_status() 
    except requests.exceptions.RequestException as e:
        # For production use, you might log this error instead of printing
        # print(f"Error fetching data for {date_str}: {e}")
        return None

    soup = BeautifulSoup(response.content, 'html.parser')
    menu_table = soup.find('table', class_='menu-list')

    # If the main table isn't found, assume no menu is available
    if not menu_table:
        return None

    menu_data = {'lunch': None, 'dinner': None}
    rows = menu_table.find_all('tr')
    meals_found = 0
    
    for row in rows:
        cols = row.find_all(['td', 'th'])
        if not cols or len(cols) < 2:
            continue
        
        meal_type_cell = cols[0].text.strip()
        
        if 'Öğle Yemeği' in meal_type_cell:
            meal_key = 'lunch'
            time_slot = LUNCH_TIME
        elif 'Akşam Yemeği' in meal_type_cell:
            meal_key = 'dinner'
            time_slot = DINNER_TIME
        else:
            continue
            
        menu_items_cell = cols[1]
        
        # --- ROBUST EXTRACTION LOGIC ---
        # Extract all text nodes within the cell, filtering out empty strings and noise.
        raw_text_nodes = menu_items_cell.find_all(text=True, recursive=True)
        
        # Clean and filter the text nodes to get a list of actual menu items.
        menu_list = [
            item.strip() 
            for item in raw_text_nodes 
            if item.strip() and not item.isspace() and item.strip() not in (',', '-', '–')
        ]
        
        # If text came as one long string, try to split by commas as a fallback
        if len(menu_list) == 1:
            temp_split = menu_list[0].split(',') 
            menu_list = [item.strip() for item in temp_split if item.strip()]

        if not menu_list:
             continue # Skip this meal if the menu list is empty
             
        # Create the Description from the entire list
        description = ", ".join(menu_list)
        
        # Create the Title from the first two items
        if len(menu_list) >= 2:
            main_course = menu_list[0]
            side_dish = menu_list[1]
            title = f"{main_course.title()} w/ {side_dish.title()}"
        else:
            main_course = menu_list[0]
            title = f"{main_course.title()} Menu"
        
        menu_data[meal_key] = {
            "Title": title,
            "Description": description,
            "Date": date_str,
            "Time": time_slot
        }
        meals_found += 1
    
    # Return data only if at least one meal was found
    return menu_data if