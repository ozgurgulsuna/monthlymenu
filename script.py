import requests
from bs4 import BeautifulSoup
from datetime import datetime, timedelta
from typing import Optional

# --- Configuration ---
BASE_URL = "https://kafeterya.metu.edu.tr/"
CALENDAR_URL_TEMPLATE = BASE_URL + "?date_filter[value][date]={date}"
LUNCH_TIME = "11:40 to 12:30 GMT+3"
DINNER_TIME = "17:40 to 18:30 GMT+3"
DEBUG = True

def fetch_and_format_menu(date_str: str) -> Optional[dict]:
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
        if DEBUG:
            print(f"[DEBUG] Fetched {response.status_code} from {response.url}")
            # Print content-type to help detect wrong content (e.g., HTML vs JSON)
            print(f"[DEBUG] Content-Type: {response.headers.get('Content-Type')}")
            # Print a safe snippet of the HTML to inspect structure (first 2000 chars)
            snippet = response.text[:2000]
            print("[DEBUG] HTML snippet (first 2000 chars):\n" + snippet)
            # Save full HTML to a debug file for offline inspection
            try:
                debug_filename = f"debug_menu_{date_str.replace('/','')}.html"
                with open(debug_filename, 'w', encoding='utf-8') as fh:
                    fh.write(response.text)
                print(f"[DEBUG] Wrote full HTML to {debug_filename}")
            except Exception as e:
                print(f"[DEBUG] Failed to write debug HTML file: {e}")
    except requests.exceptions.RequestException as e:
        if DEBUG:
            print(f"[DEBUG] Error fetching data for {date_str}: {e}")
        return None

    soup = BeautifulSoup(response.content, 'html.parser')
    menu_table = soup.find('table', class_='menu-list')
    if DEBUG:
        print(f"[DEBUG] menu_table found: {bool(menu_table)}")

    menu_data = {'lunch': None, 'dinner': None}
    meals_found = 0

    if menu_table:
        rows = menu_table.find_all('tr')
        if DEBUG:
            print(f"[DEBUG] Rows found in menu_table: {len(rows)}")
    else:
        # Alternative parser for Drupal view structure
        view_div = soup.find('div', class_='view-yemek-listesi')
        if DEBUG:
            print(f"[DEBUG] view-yemek-listesi found: {bool(view_div)}")

        if not view_div:
            return None

        # Synthesize rows from H3 titles (Öğle Yemeği / Akşam Yemeği)
        rows = []
        for header in view_div.find_all('h3', class_='title'):
            rows.append(header)
        if DEBUG:
            print(f"[DEBUG] Synthesized rows from view_div (h3.title count): {len(rows)}")
    
    print("Fetched:", response.status_code, response.url)
    print("HTML snippet:", response.text[:1000])
    print("Found menu_table:", bool(menu_table))
    print("Rows found:", len(rows) if menu_table else 0)
    
    for row in rows:
        meal_type_cell = ''
        menu_items_cell = None

        if getattr(row, 'name', None) == 'tr':
            cols = row.find_all(['td', 'th'])
            if not cols or len(cols) < 2:
                continue
            meal_type_cell = cols[0].text.strip()
            menu_items_cell = cols[1]
        else:
            # synthesized header (h3.title) from the Drupal view
            meal_type_cell = row.get_text(strip=True)
            if DEBUG:
                print(f"[DEBUG] Processing synthesized row: meal_type_cell='{meal_type_cell}'")
            # find parent that contains article entries
            parent_row = row.find_parent(lambda t: t.name == 'div' and 'views-row' in t.get('class', []))
            if not parent_row:
                parent_row = row.find_parent()
            menu_items_cell = parent_row

        if DEBUG:
            print(f"[DEBUG] meal_type_cell='{meal_type_cell}'")

        if 'Öğle' in meal_type_cell:
            meal_key = 'lunch'
            time_slot = LUNCH_TIME
        elif 'Akşam' in meal_type_cell:
            meal_key = 'dinner'
            time_slot = DINNER_TIME
        else:
            continue

        # --- ROBUST EXTRACTION LOGIC ---
        # Extract menu items depending on shape: article/h2 preferred
        raw_text_nodes = []
        if menu_items_cell:
            # Prefer extracting <article><h2> text nodes when present
            articles = menu_items_cell.find_all('article') if hasattr(menu_items_cell, 'find_all') else []
            if articles:
                for art in articles:
                    h2 = art.find('h2')
                    if h2 and h2.get_text(strip=True):
                        raw_text_nodes.append(h2.get_text(strip=True))
            else:
                # fallback: gather raw text
                raw_text_nodes = menu_items_cell.find_all(text=True, recursive=True)

        if DEBUG:
            print(f"[DEBUG] raw_text_nodes (count): {len(raw_text_nodes)}")
            print("[DEBUG] raw_text_nodes sample: ", [repr(n) for n in raw_text_nodes[:10]])

        # Clean and filter the text nodes to get a list of actual menu items.
        menu_list = [
            item.strip()
            for item in raw_text_nodes
            if item and isinstance(item, str) and item.strip() and not item.isspace() and item.strip() not in (',', '-', '–')
        ]
        if DEBUG:
            print(f"[DEBUG] menu_list after cleaning (count): {len(menu_list)}")
            print("[DEBUG] menu_list sample: ", menu_list[:10])

        # If text came as one long string, try to split by commas as a fallback
        if len(menu_list) == 1:
            temp_split = menu_list[0].split(',')
            menu_list = [item.strip() for item in temp_split if item.strip()]

        if not menu_list:
            if DEBUG:
                print("[DEBUG] menu_list empty after cleaning; skipping this meal row")
            continue

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
    return menu_data if meals_found > 0 else None

# Print the menu for today as a test
if __name__ == "__main__":
    today_str = datetime.now().strftime("%d/%m/%Y")
    menu = fetch_and_format_menu(today_str)
    print()
    print(menu)
