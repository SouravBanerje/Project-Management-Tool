from app import db
from datetime import datetime
import enum

class TaskStatus(enum.Enum):
    NOT_STARTED = 'Not Started'
    IN_PROGRESS = 'In Progress'
    COMPLETED = 'Completed'
    PENDING = 'Pending'

class Task(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    project_id = db.Column(db.Integer, db.ForeignKey('project.id'), nullable=False)
    parent_id = db.Column(db.Integer, db.ForeignKey('task.id'))
    name = db.Column(db.String(100), nullable=False)
    description = db.Column(db.Text)
    start_date = db.Column(db.Date, nullable=False)
    end_date = db.Column(db.Date, nullable=False)
    dependency_days = db.Column(db.Integer, default=0)  # Dependency UOM in days
    hours = db.Column(db.Integer)  # Calculated from start and end dates
    is_milestone = db.Column(db.Boolean, default=False)
    is_active = db.Column(db.Boolean, default=True)
    status = db.Column(db.Enum(TaskStatus), default=TaskStatus.NOT_STARTED)
    has_unread_comments = db.Column(db.Boolean, default=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    # Relationships
    subtasks = db.relationship('Task', backref=db.backref('parent', remote_side=[id]), lazy='dynamic')
    resources = db.relationship('TaskResource', backref='task', lazy='dynamic', cascade='all, delete-orphan')
    comments = db.relationship('TaskComment', backref='task', lazy='dynamic', cascade='all, delete-orphan')
    version_history = db.relationship('TaskVersionHistory', backref='task', lazy='dynamic', cascade='all, delete-orphan')
    
    def calculate_hours(self):
        """Calculate working hours between start and end date based on calendar"""
        # This will need to be implemented with calendar data
        # For now, we'll use a simplified approach (8 hours per working day)
        working_days = (self.end_date - self.start_date).days + 1
        # This is a simplification - in reality we would check against the calendar
        return working_days * 8
    
    def get_all_subtasks(self):
        """Get all subtasks recursively"""
        tasks = []
        for subtask in self.subtasks:
            tasks.append(subtask)
            tasks.extend(subtask.get_all_subtasks())
        return tasks
    
    def __repr__(self):
        return f'<Task {self.id} - {self.name}>'

class TaskComment(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    task_id = db.Column(db.Integer, db.ForeignKey('task.id'), nullable=False)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    content = db.Column(db.Text, nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    def __repr__(self):
        return f'<TaskComment {self.id}>'

class TaskResource(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    task_id = db.Column(db.Integer, db.ForeignKey('task.id'), nullable=False)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    designation = db.Column(db.String(100))
    grade = db.Column(db.String(50))
    assigned_at = db.Column(db.DateTime, default=datetime.utcnow)
    
    def __repr__(self):
        return f'<TaskResource {self.user_id} on {self.task_id}>'

class Calendar(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    date = db.Column(db.Date, unique=True, nullable=False)
    is_working_day = db.Column(db.Boolean, default=True)
    working_hours = db.Column(db.Integer, default=8)  # Default 8 hours for working days
    description = db.Column(db.String(200))  # For holidays, etc.
    
    def __repr__(self):
        return f'<Calendar {self.date}>'