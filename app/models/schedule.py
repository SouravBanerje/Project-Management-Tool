from app import db
from datetime import datetime

class ScheduleVersion(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    project_id = db.Column(db.Integer, db.ForeignKey('project.id'), nullable=False)
    version = db.Column(db.String(10), nullable=False)  # e.g., "1.0", "1.1"
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    created_by = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    notes = db.Column(db.Text)
    
    user = db.relationship('User')
    task_history = db.relationship('TaskVersionHistory', backref='schedule_version', lazy='dynamic')
    version_changes = db.relationship('VersionChangeReport', backref='schedule_version', lazy='dynamic')
    
    def __repr__(self):
        return f'<ScheduleVersion {self.project_id} - {self.version}>'

class TaskVersionHistory(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    task_id = db.Column(db.Integer, db.ForeignKey('task.id'), nullable=False)
    schedule_version_id = db.Column(db.Integer, db.ForeignKey('schedule_version.id'), nullable=False)
    start_date = db.Column(db.Date, nullable=False)
    end_date = db.Column(db.Date, nullable=False)
    status = db.Column(db.String(20))  # Status at the time of version creation
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    
    def __repr__(self):
        return f'<TaskVersionHistory {self.task_id} in {self.schedule_version_id}>'

class VersionChangeReport(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    schedule_version_id = db.Column(db.Integer, db.ForeignKey('schedule_version.id'), nullable=False)
    previous_version_id = db.Column(db.Integer, db.ForeignKey('schedule_version.id'))
    change_summary = db.Column(db.Text)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    created_by = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    
    user = db.relationship('User')
    previous_version = db.relationship('ScheduleVersion', foreign_keys=[previous_version_id])
    
    def __repr__(self):
        return f'<VersionChangeReport {self.schedule_version_id}>'