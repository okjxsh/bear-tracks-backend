import json
import os
import pickle
from datetime import datetime
from flask import Flask, request, session, redirect
from db import db, User, Event, Organization
from apiclient.discovery import build
from google_auth_oauthlib.flow import Flow
from google_auth_oauthlib.flow import InstalledAppFlow
from google.oauth2.credentials import Credentials
from apiclient.discovery import build
import requests
import scraper

# Flask app configuration
app = Flask(__name__)
app.secret_key = os.urandom(24)
db_filename = "beartracks.db"
app.config["SQLALCHEMY_DATABASE_URI"] = "sqlite:///%s" % db_filename
app.config["SQLALCHEMY_TRACK_MODIFICATIONS"] = False
app.config["SQLALCHEMY_ECHO"] = True

# Initialize the database
db.init_app(app)
with app.app_context():
    db.create_all()

# Helper functions for success and failure responses
def success_response(data, code=200):
    return json.dumps(data), code

def failure_response(message, code=404):
    return json.dumps({"error": message}), code

# iOS Mobile OAuth Login
@app.route("/login/mobile", methods=["POST"])
def mobile_login():
    data = request.json
    access_token = data.get("access_token")
    if not access_token:
        return failure_response("Access token is required", 400)

    try:
        # Use the access token to fetch user info
        credentials = Credentials(token=access_token)
        service = build("oauth2", "v2", credentials=credentials)
        user_info = service.userinfo().get().execute()

        google_user_id = user_info["id"]

        # Save user in the database
        user = User.query.filter_by(google_user_id=google_user_id).first()
        if user is None:
            user = User(
                google_user_id=google_user_id,
                token=access_token,
                refresh_token=None,
                token_uri="https://oauth2.googleapis.com/token",
                client_id="",
                client_secret="",
                scopes="https://www.googleapis.com/auth/calendar",
                name=user_info.get("name", "Unknown")
            )
            db.session.add(user)
        else:
            user.token = access_token
        db.session.commit()

        return success_response({"message": "User logged in", "user_id": google_user_id})

    except Exception as e:
        print("Error:", e)
        return failure_response("Failed to log in", 500)

"""
EVENT ROUTES
"""

@app.route("/events/fetch/", methods=["POST"])
def fetch_events():
    # Use the scraper to fetch events
    try:
        scraped_events = scraper.scrape_events() 

        return success_response({"events": scraped_events})
    except Exception as e:
        print(f"Error fetching events: {e}")
        return failure_response("Failed to fetch events", 500)

# Get all events
@app.route("/events/")
def get_all_events(): 
    events = [e.serialize() for e in Event.query.all()]
    return success_response({"events": events})

# Create an event
@app.route("/events/", methods=["POST"])
def create_event():
    body = json.loads(request.data)
    required_fields = ["name", "start_date", "start_time", "end_date", "end_time", "location", "description", "organization"]
    for field in required_fields:
        if field not in body:
            return failure_response(f"Missing required field: {field}", 400)
    
    organization = Organization.query.filter_by(name=body.get('organization')).first()
    if organization is None:
        return failure_response("Organization does not exist.", 400)

    new_event = Event(
        name=body.get('name'),
        start_date=datetime.strptime(body.get('start_date'), "%Y-%m-%d").date(),
        start_time=datetime.strptime(body.get('start_time'), "%H:%M:%S").time(), # Format: HH:MM:SS
        end_date=datetime.strptime(body.get('end_date'), "%Y-%m-%d").date(),
        end_time=datetime.strptime(body.get('end_time'), "%H:%M:%S").time(),
        location=body.get('location'),
        description=body.get('description'),
        organization=organization,
    )
    db.session.add(new_event)
    db.session.commit()
    return success_response(new_event.serialize(), 201)

# Get all events on specific date
@app.route("/events/date/<date>/")
def get_event_on_date(date):
    try:
        # Convert the string date to a Python date object
        target_date = datetime.strptime(date, "%Y-%m-%d").date()
    except ValueError:
        return failure_response("Invalid date format. Use YYYY-MM-DD")

    # Query the database for events on the specified date
    events = Event.query.filter_by(start_date=target_date).all()

    if not events:
        return failure_response(f"No events found for date {date}")

    # Serialize the events
    serialized_events = [event.serialize() for event in events]
    return success_response({"events": serialized_events})

# Get event by specified ID
@app.route("/events/<int:id>/")
def get_event_by_id(id):
    event = Event.query.filter_by(id=id).first()
    if event is None:
        return failure_response("Event not found")
    return success_response(event.serialize())

# Delete a specific event
@app.route("/events/<int:id>/", methods=["DELETE"])
def delete_event(id):
    event = Event.query.filter_by(id=id).first()
    if event is None:
        return failure_response("Event not found")
    serialized_event = event.serialize()
    db.session.delete(event)
    db.session.commit()
    return success_response(serialized_event)

"""
ORGANIZATION ROUTES
"""
# Get all organizations
@app.route("/organizations/")
def get_all_organizations(): 
    organizations = [o.serialize() for o in Organization.query.all()]
    return success_response({"organizations": organizations})

# Create an organization
@app.route("/organizations/", methods=["POST"])
def create_organization():
    body = json.loads(request.data)
    required_fields = ["name", "org_type"]
    for field in required_fields:
        if field not in body:
            return failure_response(f"Missing required field: {field}", 400)

    new_organization = Organization(
        name=body.get('name'),
        org_type=body.get('org_type')
    )
    db.session.add(new_organization)
    db.session.commit()
    return success_response(new_organization.serialize(), 201)

"""
USER ROUTES
"""
# Get all users
@app.route("/users/")
def get_users(): 
    users = [u.serialize() for u in User.query.all()]
    return success_response({"users": users})

# Get a specific user
@app.route("/users/<int:id>/")
def get_user_by_id(id):
    user = User.query.filter_by(id=id).first()
    if user is None:
        return failure_response("User not found")
    return success_response(user.serialize()) 

# Add user to event
@app.route("/events/<int:id>/add/", methods=["POST"])
def add_user_to_event(event_id):
    body = json.loads(request.data)
    required_fields = ["user_id"]
    for field in required_fields:
        if field not in body:
            return failure_response(f"Missing required field: {field}", 400)
        
    user = User.query.filter_by(id=body.get('user_id')).first()
    event = Event.query.filter_by(id=event_id).first()
    
    if user is None:
        return failure_response("User not found")
    if event is None:
        return failure_response("Event not found")
    
    if user in event.attendees:
        return failure_response("User is already a attending this event.")
    
    event.attendees.append(user)
    db.session.commit()

    # Add the event to the user's Google Calendar
    if user.token:
        try:
            credentials = Credentials(
                token=user.token,
                refresh_token=user.refresh_token,
                token_uri=user.token_uri,
                client_id=user.client_id,
                client_secret=user.client_secret,
                scopes=user.scopes.split(","),
            )
            service = build("calendar", "v3", credentials=credentials)

            # Create the event data for Google Calendar
            google_event = {
                "summary": event.name,
                "location": event.location,
                "description": event.description,
                "start": {
                    "dateTime": f"{event.start_date}T{event.start_time}",
                    "timeZone": "UTC",
                },
                "end": {
                    "dateTime": f"{event.end_date}T{event.end_time}",
                    "timeZone": "UTC",
                },
            }

            # Insert the event into the user's calendar
            created_event = service.events().insert(calendarId="primary", body=google_event).execute()
            print(f"Event created: {created_event.get('htmlLink')}")
        except Exception as e:
            return failure_response("Failed to add event to Google Calendar")
        
    return success_response(user.serialize())

# Remove user from event
@app.route("/events/<int:id>/remove/", methods=["POST"])
def remove_user_from_event(event_id):
    body = json.loads(request.data)
    required_fields = ["user_id"]
    for field in required_fields:
        if field not in body:
            return failure_response(f"Missing required field: {field}", 400)
        
    user = User.query.filter_by(id=body.get('user_id')).first()
    event = Event.query.filter_by(id=event_id).first()
    
    if user is None:
        return failure_response("User not found")
    if event is None:
        return failure_response("Event not found")
    
    if user not in event.attendees:
        return failure_response("User is not part of this event.", 400)
    
    event.attendees.remove(user)
    db.session.commit()

    # Remove the event from the user's Google Calendar
    if user.token:
        try:
            credentials = Credentials(
                token=user.token,
                refresh_token=user.refresh_token,
                token_uri=user.token_uri,
                client_id=user.client_id,
                client_secret=user.client_secret,
                scopes=user.scopes.split(","),
            )
            service = build("calendar", "v3", credentials=credentials)

            # Assume you have stored the Google Calendar event ID in your database
            google_event_id = event.google_calendar_event_id
            if google_event_id:
                service.events().delete(calendarId="primary", eventId=google_event_id).execute()
        except Exception as e:
            return failure_response("Failed to remove event from Google Calendar")
        
    return success_response(user.serialize())

if __name__ == "__main__":
    app.run(debug=True)