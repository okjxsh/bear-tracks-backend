from datetime import datetime
from bs4 import BeautifulSoup  # To clean HTML tags
from db import db, Event, Organization  # Importing models from your db.py
import requests

# Utility function to parse event dates and times
def parse_event_dates(date_string):
    """Parse date and time information from the given string."""
    try:
        clean_date_string = BeautifulSoup(date_string, "html.parser").get_text()
        date_parts = clean_date_string.split("\u2013")  # Use \u2013 for &ndash;

        if len(date_parts) != 2:
            raise ValueError("Invalid date format")

        # Define additional date-time formats
        date_formats = [
            "%a, %b %d, %Y %I:%M %p",  # Full date and time
            "%a, %b %d, %Y %I:%M %p %Z",  # With timezone
            "%a, %b %d, %Y %I %p",  # Without colon in time
            "%a, %b %d, %Y",  # Only date
        ]

        start_date = end_date = None

        for fmt in date_formats:
            try:
                start_date = datetime.strptime(date_parts[0].strip(), fmt)
                break
            except ValueError:
                continue

        for fmt in date_formats:
            try:
                end_date = datetime.strptime(date_parts[1].strip(), fmt)
                break
            except ValueError:
                continue

        if not start_date or not end_date:
            raise ValueError("Failed to parse start or end date")

        return start_date, end_date
    except Exception as e:
        print(f"Error parsing dates: {e}")
        return None, None


# Scraper function to fetch and process events
def scrape_events():
    """Scrape events and save them to the database."""
    try:
        url = "https://cornell.campusgroups.com/mobile_ws/v17/mobile_events_list?range=0&limit=40&filter4_contains=OR&filter4_notcontains=OR&order=undefined&search_word=&&1733532882139"
        response = requests.get(url)
        events_data = response.json()

        for item in events_data:
            # Skip if required fields are missing
            if not item.get("p3") or not item.get("p4"):
                continue

            try:
                # Parse start and end dates
                start_datetime, end_datetime = parse_event_dates(item["p4"])
                if not start_datetime or not end_datetime:
                    continue

                # Extract other event details
                name = item.get("p3")
                location = BeautifulSoup(item.get("p6", ""), "html.parser").get_text()
                organization_name = item.get("p9")
                description = BeautifulSoup(item.get("p30", ""), "html.parser").get_text()
                event_url = item.get("p18")

                # Find or create the organization
                organization = Organization.query.filter_by(name=organization_name).first()
                if not organization:
                    organization = Organization(name=organization_name, org_type="Unknown")
                    db.session.add(organization)
                    db.session.commit()

                # Create the event object
                event = Event(
                    name=name,
                    start_date=start_datetime.date(),
                    start_time=start_datetime.time(),
                    end_date=end_datetime.date(),
                    end_time=end_datetime.time(),
                    location=location,
                    description=description,
                    event_url=event_url,
                    organization_id=organization.id
                )
                db.session.add(event)
                db.session.commit()
                print(f"Event saved: {name}")

            except Exception as e:
                print(f"Error processing item {item}: {e}")
                continue

    except requests.exceptions.RequestException as e:
        print(f"Request error: {e}")
    except ValueError as e:
        print(f"JSON parsing error: {e}")

if __name__ == "__main__":
    scrape_events()
