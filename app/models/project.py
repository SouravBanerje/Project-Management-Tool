from app import db
from datetime import datetime
import enum

class ProjectType(enum.Enum):
    FIXED_PRICE = 'Fixed Price'
    TM_PRICE = 'T&M Price'

class ProjectStatus(enum.Enum):
    ENTERED = 'Entered'
    APPROVED_ACTIVE = 'Approved & Active'
    CANCELED = 'Canceled'
    COMPLETED = 'Completed'

class Project(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    project_id = db.Column(db.String(5), unique=True, nullable=False)  # 5-digit numeric ID
    name = db.Column(db.String(100), nullable=False)
    description = db.Column(db.Text)
    start_date = db.Column(db.Date, nullable=False)
    end_date = db.Column(db.Date, nullable=False)
    project_type = db.Column(db.Enum(ProjectType), nullable=False)
    total_amount = db.Column(db.Numeric(10, 2))  # For Fixed Price projects
    monthly_billing = db.Column(db.Numeric(10, 2))  # For T&M projects
    project_manager_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    customer_po_number = db.Column(db.String(50))
    status = db.Column(db.Enum(ProjectStatus), default=ProjectStatus.ENTERED)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    # Relationships
    tasks = db.relationship('Task', backref='project', lazy='dynamic', cascade='all, delete-orphan')
    versions = db.relationship('ProjectVersion', backref='project', lazy='dynamic', cascade='all, delete-orphan')
    po_attachments = db.relationship('POAttachment', backref='project', lazy='dynamic', cascade='all, delete-orphan')
    sow_attachments = db.relationship('SOWAttachment', backref='project', lazy='dynamic', cascade='all, delete-orphan')
    schedule_versions = db.relationship('ScheduleVersion', backref='project', lazy='dynamic', cascade='all, delete-orphan')
    
    def __init__(self, name, start_date, end_date, project_type, project_manager_id, **kwargs):
        self.name = name
        self.start_date = start_date
        self.end_date = end_date
        self.project_type = project_type
        self.project_manager_id = project_manager_id
        
        # Set optional fields if provided
        for key, value in kwargs.items():
            if hasattr(self, key):
                setattr(self, key, value)
        
        # Generate project_id after saving to database
        # This will be done in a post-save event or in the route
    
    def calculate_duration(self):
        """Calculate project duration in days"""
        return (self.end_date - self.start_date).days
    
    def __repr__(self):
        return f'<Project {self.project_id} - {self.name}>'

class ProjectVersion(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    project_id = db.Column(db.Integer, db.ForeignKey('project.id'), nullable=False)
    version = db.Column(db.String(10), nullable=False)  # e.g., "1.0", "1.1"
    changes = db.Column(db.Text)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    created_by = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    
    user = db.relationship('User')
    
    def __repr__(self):
        return f'<ProjectVersion {self.project_id} - {self.version}>'

class POAttachment(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    project_id = db.Column(db.Integer, db.ForeignKey('project.id'), nullable=False)
    filename = db.Column(db.String(255), nullable=False)
    file_path = db.Column(db.String(255), nullable=False)
    uploaded_at = db.Column(db.DateTime, default=datetime.utcnow)
    uploaded_by = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    
    user = db.relationship('User')
    
    def __repr__(self):
        return f'<POAttachment {self.filename}>'

class SOWAttachment(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    project_id = db.Column(db.Integer, db.ForeignKey('project.id'), nullable=False)
    filename = db.Column(db.String(255), nullable=False)
    file_path = db.Column(db.String(255), nullable=False)
    uploaded_at = db.Column(db.DateTime, default=datetime.utcnow)
    uploaded_by = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    
    user = db.relationship('User')
    
    def __repr__(self):
        return f'<SOWAttachment {self.filename}>'