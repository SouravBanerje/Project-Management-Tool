from flask_wtf import FlaskForm
from wtforms import StringField, TextAreaField, SelectField, DateField, BooleanField, IntegerField, SubmitField
from wtforms.validators import DataRequired, Optional, Length, NumberRange
from app.models.task import TaskStatus

class TaskForm(FlaskForm):
    name = StringField('Task Name', validators=[DataRequired(), Length(max=100)])
    description = TextAreaField('Task Description', validators=[Optional(), Length(max=500)])
    start_date = DateField('Start Date', format='%Y-%m-%d', validators=[DataRequired()])
    end_date = DateField('End Date', format='%Y-%m-%d', validators=[DataRequired()])
    dependency_days = IntegerField('Dependency (days)', validators=[Optional(), NumberRange(min=0)], default=0)
    is_milestone = BooleanField('Is Milestone', default=False)
    is_active = BooleanField('Is Active', default=True)
    status = SelectField('Status', choices=[(s.name, s.value) for s in TaskStatus], validators=[DataRequired()])
    parent_id = SelectField('Parent Task', validators=[Optional()], coerce=int)
    submit = SubmitField('Save Task')

    def validate_end_date(self, end_date):
        if end_date.data < self.start_date.data:
            raise ValueError('End date must be after start date')

class TaskCommentForm(FlaskForm):
    content = TextAreaField('Comment', validators=[DataRequired(), Length(max=1000)])
    submit = SubmitField('Add Comment')

class TaskResourceForm(FlaskForm):
    user_id = SelectField('Team Member', validators=[DataRequired()], coerce=int)
    designation = StringField('Designation', validators=[Optional(), Length(max=100)])
    grade = StringField('Grade', validators=[Optional(), Length(max=50)])
    submit = SubmitField('Assign Resource')

class TaskFilterForm(FlaskForm):
    status = SelectField('Status', choices=[('', 'All')] + [(s.name, s.value) for s in TaskStatus], validators=[Optional()])
    start_date_from = DateField('Start Date From', format='%Y-%m-%d', validators=[Optional()])
    start_date_to = DateField('Start Date To', format='%Y-%m-%d', validators=[Optional()])
    resource_id = SelectField('Assigned To', validators=[Optional()], coerce=int)
    is_milestone = BooleanField('Milestones Only', default=False)
    submit = SubmitField('Filter')