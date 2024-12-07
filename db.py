from flask_sqlalchemy import SQLAlchemy

db = SQLAlchemy()

events_users = db.Table(
    'events_users',
    db.Column('event_id', db.Integer, db.ForeignKey('event.id'), primary_key=True),
    db.Column('user_id', db.Integer, db.ForeignKey('user.id'), primary_key=True)
)

class User(db.Model):
    __tablename__ = "user"

    id = db.Column(db.Integer, primary_key=True)
    google_user_id = db.Column(db.String, unique=True, nullable=False)
    token = db.Column(db.String, nullable=False)
    refresh_token = db.Column(db.String, nullable=True)
    token_uri = db.Column(db.String, nullable=False)
    client_id = db.Column(db.String, nullable=False)
    client_secret = db.Column(db.String, nullable=False)
    scopes = db.Column(db.String, nullable=False)
    name = db.Column(db.String, nullable=True)
    events = db.relationship("Event", secondary=events_users, back_populates='attendees')

    def serialize(self):
        return {
            "id": self.id,
            "google_user_id": self.google_user_id,
            "name": self.name
        }

class Organization(db.Model):    
    __tablename__ = "organization"    
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String, nullable=False)
    org_type = db.Column(db.String, nullable=False)
    events = db.relationship("Event", cascade="delete", back_populates="organization")
    
    def serialize(self):
        return {        
            "id": self.id,          
            "name": self.name, 
            "org_type": self.org_type,
            "events": [e.serialize() for e in self.events],
        }
    
    def serialize_without_events(self):
        return {        
            "id": self.id,          
            "name": self.name, 
            "org_type": self.org_type,
        }

class Event(db.Model):    
    __tablename__ = "event"    
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String, nullable=False)
    start_date = db.Column(db.Date, nullable=False)
    start_time = db.Column(db.Time, nullable=False)
    end_date = db.Column(db.Date, nullable=True)
    end_time = db.Column(db.Time, nullable=True)
    location = db.Column(db.String, nullable=False)
    description = db.Column(db.String, nullable=False)
    event_url = db.Column(db.String)
    organization_id = db.Column(db.Integer, db.ForeignKey('organization.id'), nullable=False)
    organization = db.relationship("Organization", back_populates="events")
    attendees = db.relationship("User", secondary=events_users, back_populates='events')
    
    def serialize(self):
        return {        
            "id": self.id,        
            "name": self.name,        
            "start_date": str(self.start_date), 
            "start_time": str(self.start_time),
            "end_date": str(self.end_date),
            "end_time": str(self.end_time),
            "location": self.location,
            "description": self.event_type,
            "event_url": self.event_url,
            "organization": self.organization.serialize_without_events() if self.organization else None,
            "attendees": [a.serialize() for a in self.attendees],
        }
