
import json
import os
import sys
from playwright.sync_api import sync_playwright
from src.main import main as analyze_reviews

# Ensure UTF-8 encoding for console output
sys.stdout.reconfigure(encoding='utf-8')

def scrape_full_reviews_to_json(url, output_file="data/reviews.json", max_pages=5):
    """
    Scrapes reviews from OpenRice across multiple pages and saves them to a JSON file.
    
    Args:
        url (str): The URL of the restaurant to scrape reviews from.
        output_file (str): The path to the JSON file where reviews will be saved.
        max_pages (int, optional): Maximum number of pages to scrape. Scrapes all pages if None.
    """

    with sync_playwright() as p:
        # Launch browser in headless mode
        browser = p.chromium.launch(headless=True, slow_mo=50)
        context = browser.new_context(
            user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/112.0.0.0 Safari/537.36"
        )
        
        # Set additional headers to handle region and cookies
        context.set_extra_http_headers({
            "Accept-Language": "zh-HK",
        })

        page = context.new_page()

        try:
            # Go to the initial URL
            page.goto(url, timeout=60000, wait_until="load")

            # Handle cookie consent or redirects
            if page.locator("button:has-text('同意')").count() > 0:
                page.locator("button:has-text('同意')").click()

            all_reviews = []
            current_page = 1

            while True:
                print(f"Scraping page {current_page}...")

                # Wait for the main review container to load with increased timeout
                page.wait_for_selector("div.sr2-review-list-container", timeout=60000)  # Increased timeout to 60 seconds

                # Debugging log to confirm page navigation
                print(f"Navigated to URL: {url}")

                # Check if the selector exists before proceeding
                if not page.locator("div.sr2-review-list-container").count():
                    raise Exception("Review container not found on the page. Please verify the URL or page structure.")

                # Locate review containers
                review_containers = page.locator("div.sr2-review-list-container")

                for i in range(review_containers.count()):
                    review = review_containers.nth(i)

                    # Extract full review content while excluding image-related elements
                    try:
                        review_text = review.locator("div.content.content-full.js-content-full div.text").evaluate("""
                            element => {
                                // Remove all <a> and <img> tags from the content
                                const links = element.querySelectorAll('a');
                                const images = element.querySelectorAll('img');
                                links.forEach(link => link.remove());
                                images.forEach(image => image.remove());
                                return element.innerText; // Return only the remaining plain text
                            }
                        """)

                        # Format the review into paragraphs by splitting on line breaks
                        paragraphs = [para.strip() for para in review_text.split("\n") if para.strip()]
                        formatted_text = "\n\n".join(paragraphs)  # Join paragraphs with double line breaks
                    except Exception as e:
                        print(f"Error extracting full review text for review {i + 1}: {e}")
                        formatted_text = "Failed to extract review text"

                    # Extract review date
                    try:
                        review_date = review.locator("span[itemprop='datepublished']").inner_text()
                    except Exception as e:
                        print(f"Error extracting review date for review {i + 1}: {e}")
                        review_date = "Unknown"

                    # Extract rating with a shorter timeout and fallback to default
                    try:
                        rating_locator = review.locator("meta[itemprop='ratingvalue']")
                        if rating_locator.count() > 0:
                            rating = rating_locator.get_attribute("content", timeout=5000)  # 5-second timeout
                            rating = int(rating.strip()) if rating else 0
                        else:
                            print(f"Rating not found for review {i + 1}.")
                            rating = 0  # Default rating
                    except Exception as e:
                        print(f"Error extracting rating for review {i + 1}: {e}")
                        rating = 0  # Default rating

                    # Add review data to the list
                    all_reviews.append({
                        "date": review_date,
                        "text": formatted_text.strip(),
                        "rating": rating,
                    })

                # Check if there is a "next page" button and navigate to the next page
                next_button = page.locator("a.pagination-button.next.js-next:last-child")  # Refined locator
                if next_button.count() > 0 and (max_pages is None or current_page < max_pages):
                    next_button.click()
                    page.wait_for_timeout(3000)  # Wait for the next page to load
                    current_page += 1
                else:
                    print("No more pages to scrape or reached max page limit.")
                    break

            # Ensure the output directory exists
            os.makedirs(os.path.dirname(output_file), exist_ok=True)

            # Save reviews to a JSON file in the specified directory with UTF-8 encoding
            with open(output_file, "w", encoding="utf-8") as f:
                json.dump(all_reviews, f, ensure_ascii=False, indent=4)

            print(f"📦 Reviews saved to {output_file}")

            # Automatically pass the data to main.py for further analysis
            print("Starting analysis of the scraped data...")
            analyze_reviews()
            print("Analysis completed. Results are available in result.html.")

        except Exception as e:
            print(f"An error occurred during the scraping process: {e}")

        finally:
            browser.close()
