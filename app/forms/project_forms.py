from flask_wtf import FlaskForm
from flask_wtf.file import FileField, FileAllowed, FileRequired
from wtforms import StringField, TextAreaField, SelectField, DecimalField, DateField, SubmitField
from wtforms.validators import DataRequired, Optional, Length, NumberRange
from app.models.project import ProjectType, ProjectStatus

class ProjectForm(FlaskForm):
    name = StringField('Project Name', validators=[DataRequired(), Length(max=100)])
    description = TextAreaField('Project Description', validators=[Optional(), Length(max=1000)])
    start_date = DateField('Start Date', format='%Y-%m-%d', validators=[DataRequired()])
    end_date = DateField('End Date', format='%Y-%m-%d', validators=[DataRequired()])
    project_type = SelectField('Project Type', choices=[(t.name, t.value) for t in ProjectType], validators=[DataRequired()])
    total_amount = DecimalField('Total Amount', validators=[Optional(), NumberRange(min=0)], places=2)
    monthly_billing = DecimalField('Monthly Billing', validators=[Optional(), NumberRange(min=0)], places=2)
    project_manager_id = SelectField('Project Manager', validators=[DataRequired()], coerce=int)
    customer_po_number = StringField('Customer PO Number', validators=[Optional(), Length(max=50)])
    status = SelectField('Project Status', choices=[(s.name, s.value) for s in ProjectStatus], validators=[DataRequired()])
    po_attachment = FileField('PO Attachment', validators=[
        Optional(),
        FileAllowed(['pdf', 'doc', 'docx', 'jpg', 'png'], 'Only PDF, Word documents and images are allowed.')
    ])
    sow_attachment = FileField('SOW Attachment', validators=[
        Optional(),
        FileAllowed(['pdf', 'doc', 'docx'], 'Only PDF and Word documents are allowed.')
    ])
    submit = SubmitField('Save Project')

    def validate_end_date(self, end_date):
        if end_date.data < self.start_date.data:
            raise ValueError('End date must be after start date')

class ProjectSearchForm(FlaskForm):
    project_id = StringField('Project ID', validators=[Optional()])
    name = StringField('Project Name', validators=[Optional()])
    status = SelectField('Status', choices=[('', 'All')] + [(s.name, s.value) for s in ProjectStatus], validators=[Optional()])
    project_manager_id = SelectField('Project Manager', validators=[Optional()], coerce=int, default='')
    start_date_from = DateField('Start Date From', format='%Y-%m-%d', validators=[Optional()])
    start_date_to = DateField('Start Date To', format='%Y-%m-%d', validators=[Optional()])
    submit = SubmitField('Search')

    def __init__(self, *args, **kwargs):
        super(ProjectSearchForm, self).__init__(*args, **kwargs)
        # The project manager choices will be set in the route

class ProjectVersionForm(FlaskForm):
    changes = TextAreaField('Changes', validators=[DataRequired(), Length(max=1000)])
    submit = SubmitField('Create New Version')