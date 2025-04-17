from flask import Blueprint, render_template, redirect, url_for
from flask_login import login_required, current_user
from app.models.project import Project, ProjectStatus
from app.models.task import Task, TaskResource, TaskStatus
from sqlalchemy import func
from datetime import datetime, timedelta
from app import db
main_bp = Blueprint('main', __name__)

@main_bp.route('/')
def index():
    if current_user.is_authenticated:
        return redirect(url_for('main.dashboard'))
    return redirect(url_for('auth.login'))

@main_bp.route('/dashboard')
@login_required
def dashboard():
    # Get counts for dashboard statistics
    active_projects_count = Project.query.filter_by(status=ProjectStatus.APPROVED_ACTIVE).count()
    
    # For project managers, show only their projects
    if current_user.role.name == 'PROJECT_MANAGER':
        active_projects = Project.query.filter_by(
            project_manager_id=current_user.id,
            status=ProjectStatus.APPROVED_ACTIVE
        ).all()
        
        # Tasks assigned to their projects
        project_ids = [project.id for project in active_projects]
        tasks_due_soon = Task.query.filter(
            Task.project_id.in_(project_ids),
            Task.end_date.between(datetime.now().date(), datetime.now().date() + timedelta(days=7)),
            Task.status != TaskStatus.COMPLETED
        ).order_by(Task.end_date).limit(5).all()
        
    else:
        # For admin, show all projects
        active_projects = Project.query.filter_by(status=ProjectStatus.APPROVED_ACTIVE).limit(5).all()
        
        # For team members, show tasks assigned to them
        if current_user.role.name == 'TEAM_MEMBER':
            # Get tasks where user is assigned as a resource
            resource_task_ids = db.session.query(TaskResource.task_id).filter_by(user_id=current_user.id).all()
            resource_task_ids = [task_id for (task_id,) in resource_task_ids]
            
            tasks_due_soon = Task.query.filter(
                Task.id.in_(resource_task_ids),
                Task.end_date.between(datetime.now().date(), datetime.now().date() + timedelta(days=7)),
                Task.status != TaskStatus.COMPLETED
            ).order_by(Task.end_date).limit(5).all()
        else:
            # Admin sees all upcoming tasks
            tasks_due_soon = Task.query.filter(
                Task.end_date.between(datetime.now().date(), datetime.now().date() + timedelta(days=7)),
                Task.status != TaskStatus.COMPLETED
            ).order_by(Task.end_date).limit(5).all()
    
    # Tasks with unread comments
    if current_user.role.name == 'PROJECT_MANAGER':
        tasks_with_comments = Task.query.join(Project).filter(
            Task.has_unread_comments == True,
            Project.project_manager_id == current_user.id
        ).limit(5).all()
    elif current_user.role.name == 'TEAM_MEMBER':
        resource_task_ids = db.session.query(TaskResource.task_id).filter_by(user_id=current_user.id).all()
        resource_task_ids = [task_id for (task_id,) in resource_task_ids]
        
        tasks_with_comments = Task.query.filter(
            Task.id.in_(resource_task_ids),
            Task.has_unread_comments == True
        ).limit(5).all()
    else:
        # Admin sees all tasks with unread comments
        tasks_with_comments = Task.query.filter_by(has_unread_comments=True).limit(5).all()
    
    # Project status counts for chart
    project_status_counts = db.session.query(
        Project.status, func.count(Project.id)
    ).group_by(Project.status).all()
    
    status_data = {status.value: count for status, count in project_status_counts}
    
    context = {
        'active_projects_count': active_projects_count,
        'active_projects': active_projects,
        'tasks_due_soon': tasks_due_soon,
        'tasks_with_comments': tasks_with_comments,
        'status_data': status_data
    }
    
    return render_template('dashboard.html', **context)

@main_bp.route('/home')
@login_required
def home():
    return render_template('index.html')