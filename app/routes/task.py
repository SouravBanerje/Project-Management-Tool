from flask import Blueprint, render_template, redirect, url_for, flash, request, jsonify, current_app
from flask_login import login_required, current_user
from app import db
from app.models.user import User, UserRole
from app.models.project import Project, ProjectStatus
from app.models.task import Task, TaskStatus, TaskResource, TaskComment
from app.models.schedule import ScheduleVersion, TaskVersionHistory, VersionChangeReport
from app.forms.task_forms import TaskForm, TaskCommentForm, TaskResourceForm, TaskFilterForm
from datetime import datetime, timedelta
import json

task_bp = Blueprint('task', __name__, url_prefix='/tasks')

@task_bp.route('/project/<int:project_id>')
@login_required
def project_tasks(project_id):
    project = Project.query.get_or_404(project_id)
    
    # Check permissions for project managers
    if current_user.role == UserRole.PROJECT_MANAGER and project.project_manager_id != current_user.id:
        flash('You do not have permission to view this project.', 'danger')
        return redirect(url_for('project.index'))
    
    # Filter form
    form = TaskFilterForm()
    
    # Populate resource dropdown
    resources = User.query.all()
    form.resource_id.choices = [(0, 'All')] + [(user.id, user.get_full_name()) for user in resources]
    
    # Get filters from request
    status = request.args.get('status', '')
    resource_id = request.args.get('resource_id', type=int)
    is_milestone = request.args.get('is_milestone', type=bool)
    
    # Build query
    query = Task.query.filter_by(project_id=project_id, parent_id=None)  # Top-level tasks only
    
    if status:
        query = query.filter(Task.status == TaskStatus[status])
    
    if resource_id and resource_id > 0:
        # Find tasks where this user is assigned
        task_ids = db.session.query(TaskResource.task_id).filter_by(user_id=resource_id).all()
        task_ids = [task_id for (task_id,) in task_ids]
        query = query.filter(Task.id.in_(task_ids))
    
    if is_milestone:
        query = query.filter_by(is_milestone=True)
    
    # Get tasks
    tasks = query.order_by(Task.start_date).all()
    
    # For each task, get its children
    for task in tasks:
        task.child_tasks = task.subtasks.all()
    
    return render_template(
        'task/project_tasks.html',
        project=project,
        tasks=tasks,
        form=form
    )

@task_bp.route('/create/<int:project_id>', methods=['GET', 'POST'])
@login_required
def create(project_id):
    project = Project.query.get_or_404(project_id)
    
    # Check permissions
    if current_user.role == UserRole.TEAM_MEMBER:
        flash('You do not have permission to create tasks.', 'danger')
        return redirect(url_for('task.project_tasks', project_id=project_id))
    
    if current_user.role == UserRole.PROJECT_MANAGER and project.project_manager_id != current_user.id:
        flash('You can only add tasks to your own projects.', 'danger')
        return redirect(url_for('project.index'))
    
    form = TaskForm()
    
    # Populate parent task dropdown
    parent_tasks = Task.query.filter_by(project_id=project_id, parent_id=None).all()
    form.parent_id.choices = [(0, 'None')] + [(task.id, task.name) for task in parent_tasks]
    
    if form.validate_on_submit():
        try:
            # Create new task
            task = Task(
                project_id=project_id,
                name=form.name.data,
                description=form.description.data,
                start_date=form.start_date.data,
                end_date=form.end_date.data,
                dependency_days=form.dependency_days.data,
                is_milestone=form.is_milestone.data,
                is_active=form.is_active.data,
                status=TaskStatus[form.status.data]
            )
            
            # Set parent if selected
            if form.parent_id.data and form.parent_id.data > 0:
                task.parent_id = form.parent_id.data
            
            # Calculate hours
            task.hours = task.calculate_hours()
            
            db.session.add(task)
            db.session.commit()
            
            # If we have a schedule version, add this task to it
            latest_schedule = ScheduleVersion.query.filter_by(project_id=project_id).order_by(
                ScheduleVersion.created_at.desc()).first()
            
            if latest_schedule:
                task_history = TaskVersionHistory(
                    task_id=task.id,
                    schedule_version_id=latest_schedule.id,
                    start_date=task.start_date,
                    end_date=task.end_date,
                    status=task.status.name
                )
                db.session.add(task_history)
                db.session.commit()
            else:
                # Create initial schedule version
                new_schedule = ScheduleVersion(
                    project_id=project_id,
                    version="1.0",
                    created_by=current_user.id,
                    notes="Initial schedule creation"
                )
                db.session.add(new_schedule)
                db.session.commit()
                
                task_history = TaskVersionHistory(
                    task_id=task.id,
                    schedule_version_id=new_schedule.id,
                    start_date=task.start_date,
                    end_date=task.end_date,
                    status=task.status.name
                )
                db.session.add(task_history)
                db.session.commit()
            
            flash(f'Task "{task.name}" has been created', 'success')
            return redirect(url_for('task.project_tasks', project_id=project_id))
            
        except Exception as e:
            db.session.rollback()
            flash(f'Error creating task: {str(e)}', 'danger')
    
    # Default to project start/end dates
    if not form.start_date.data:
        form.start_date.data = project.start_date
    if not form.end_date.data:
        form.end_date.data = project.end_date
    
    return render_template('task/create.html', form=form, project=project)

@task_bp.route('/<int:task_id>')
@login_required
def view(task_id):
    task = Task.query.get_or_404(task_id)
    project = Project.query.get_or_404(task.project_id)
    
    # Check permissions for project managers
    if current_user.role == UserRole.PROJECT_MANAGER and project.project_manager_id != current_user.id:
        flash('You do not have permission to view this task.', 'danger')
        return redirect(url_for('project.index'))
    
    # Get parent task if exists
    parent_task = None
    if task.parent_id:
        parent_task = Task.query.get(task.parent_id)
    
    # Get resources
    resources = TaskResource.query.filter_by(task_id=task.id).all()
    resource_users = []
    for resource in resources:
        user = User.query.get(resource.user_id)
        resource_users.append({
            'user': user,
            'designation': resource.designation,
            'grade': resource.grade
        })
    
    # Get comments
    comments = TaskComment.query.filter_by(task_id=task.id).order_by(TaskComment.created_at).all()
    
    # Get subtasks if any
    subtasks = task.subtasks.all()
    
    # Mark comments as read if needed
    if task.has_unread_comments:
        task.has_unread_comments = False
        db.session.commit()
    
    # Comment form
    comment_form = TaskCommentForm()
    
    return render_template(
        'task/view.html',
        task=task,
        project=project,
        parent_task=parent_task,
        resources=resource_users,
        comments=comments,
        subtasks=subtasks,
        comment_form=comment_form
    )

@task_bp.route('/<int:task_id>/edit', methods=['GET', 'POST'])
@login_required
def edit(task_id):
    task = Task.query.get_or_404(task_id)
    project = Project.query.get_or_404(task.project_id)
    
    # Check permissions
    if current_user.role == UserRole.TEAM_MEMBER:
        flash('You do not have permission to edit tasks.', 'danger')
        return redirect(url_for('task.view', task_id=task.id))
    
    if current_user.role == UserRole.PROJECT_MANAGER and project.project_manager_id != current_user.id:
        flash('You can only edit tasks in your own projects.', 'danger')
        return redirect(url_for('project.index'))
    
    form = TaskForm(obj=task)
    
    # Populate parent task dropdown (excluding the current task and its children)
    parent_tasks = Task.query.filter_by(project_id=project.id, parent_id=None).all()
    # Remove current task and its subtasks from parent choices to prevent circular references
    valid_parents = []
    for potential_parent in parent_tasks:
        if potential_parent.id != task.id and task.id not in [sub.id for sub in potential_parent.get_all_subtasks()]:
            valid_parents.append((potential_parent.id, potential_parent.name))
    
    form.parent_id.choices = [(0, 'None')] + valid_parents
    
    # Convert enum values to form values
    form.status.data = task.status.name
    
    if form.validate_on_submit():
        try:
            old_data = {
                'name': task.name,
                'description': task.description,
                'start_date': task.start_date,
                'end_date': task.end_date,
                'dependency_days': task.dependency_days,
                'is_milestone': task.is_milestone,
                'is_active': task.is_active,
                'status': task.status,
                'parent_id': task.parent_id
            }
            
            # Update task data
            task.name = form.name.data
            task.description = form.description.data
            task.start_date = form.start_date.data
            task.end_date = form.end_date.data
            task.dependency_days = form.dependency_days.data
            task.is_milestone = form.is_milestone.data
            task.is_active = form.is_active.data
            task.status = TaskStatus[form.status.data]
            
            # Set parent if selected
            if form.parent_id.data and form.parent_id.data > 0:
                task.parent_id = form.parent_id.data
            else:
                task.parent_id = None
            
            # Re-calculate hours
            task.hours = task.calculate_hours()
            
            # Check if there were significant changes
            has_changes = False
            for key, old_value in old_data.items():
                new_value = getattr(task, key)
                if old_value != new_value:
                    has_changes = True
                    break
            
            if has_changes:
                # Get the latest schedule version
                latest_schedule = ScheduleVersion.query.filter_by(project_id=project.id).order_by(
                    ScheduleVersion.created_at.desc()).first()
                
                if latest_schedule:
                    # Create a new schedule version
                    major, minor = latest_schedule.version.split('.')
                    new_version = f"{major}.{int(minor) + 1}"
                    
                    new_schedule = ScheduleVersion(
                        project_id=project.id,
                        version=new_version,
                        created_by=current_user.id,
                        notes=f"Task '{task.name}' updated"
                    )
                    db.session.add(new_schedule)
                    db.session.commit()
                    
                    # Record the task version history
                    task_history = TaskVersionHistory(
                        task_id=task.id,
                        schedule_version_id=new_schedule.id,
                        start_date=task.start_date,
                        end_date=task.end_date,
                        status=task.status.name
                    )
                    db.session.add(task_history)
                    
                    # Create change report
                    changes = []
                    if task.name != old_data['name']:
                        changes.append(f"Name changed from '{old_data['name']}' to '{task.name}'")
                    if task.start_date != old_data['start_date']:
                        changes.append(f"Start date changed from {old_data['start_date']} to {task.start_date}")
                    if task.end_date != old_data['end_date']:
                        changes.append(f"End date changed from {old_data['end_date']} to {task.end_date}")
                    if task.status != old_data['status']:
                        changes.append(f"Status changed from {old_data['status'].value} to {task.status.value}")
                    
                    version_report = VersionChangeReport(
                        schedule_version_id=new_schedule.id,
                        previous_version_id=latest_schedule.id,
                        change_summary="\n".join(changes),
                        created_by=current_user.id
                    )
                    db.session.add(version_report)
            
            db.session.commit()
            
            flash(f'Task "{task.name}" has been updated', 'success')
            return redirect(url_for('task.view', task_id=task.id))
            
        except Exception as e:
            db.session.rollback()
            flash(f'Error updating task: {str(e)}', 'danger')
    
    return render_template('task/edit.html', form=form, task=task, project=project)

@task_bp.route('/<int:task_id>/comment', methods=['POST'])
@login_required
def add_comment(task_id):
    task = Task.query.get_or_404(task_id)
    form = TaskCommentForm()
    
    if form.validate_on_submit():
        # Create new comment
        comment = TaskComment(
            task_id=task_id,
            user_id=current_user.id,
            content=form.content.data
        )
        db.session.add(comment)
        
        # Mark task as having unread comments
        task.has_unread_comments = True
        db.session.commit()
        
        flash('Comment added successfully', 'success')
    else:
        flash('Error adding comment', 'danger')
    
    return redirect(url_for('task.view', task_id=task_id))

@task_bp.route('/<int:task_id>/resources', methods=['GET', 'POST'])
@login_required
def manage_resources(task_id):
    task = Task.query.get_or_404(task_id)
    project = Project.query.get_or_404(task.project_id)
    
    # Check permissions
    if current_user.role == UserRole.TEAM_MEMBER:
        flash('You do not have permission to manage task resources.', 'danger')
        return redirect(url_for('task.view', task_id=task.id))
    
    if current_user.role == UserRole.PROJECT_MANAGER and project.project_manager_id != current_user.id:
        flash('You can only manage resources for tasks in your own projects.', 'danger')
        return redirect(url_for('project.index'))
    
    form = TaskResourceForm()
    
    # Populate user dropdown
    users = User.query.filter(User.role != UserRole.ADMIN).all()  # Exclude admin users from resource assignment
    form.user_id.choices = [(user.id, user.get_full_name()) for user in users]
    
    # Get existing resources
    resources = TaskResource.query.filter_by(task_id=task.id).all()
    resource_users = []
    for resource in resources:
        user = User.query.get(resource.user_id)
        resource_users.append({
            'id': resource.id,
            'user': user,
            'designation': resource.designation,
            'grade': resource.grade
        })
    
    if form.validate_on_submit():
        # Check if user is already assigned
        existing = TaskResource.query.filter_by(task_id=task_id, user_id=form.user_id.data).first()
        if existing:
            flash('This user is already assigned to the task.', 'warning')
        else:
            # Assign new resource
            resource = TaskResource(
                task_id=task_id,
                user_id=form.user_id.data,
                designation=form.designation.data,
                grade=form.grade.data
            )
            db.session.add(resource)
            db.session.commit()
            
            flash('Resource assigned successfully', 'success')
            return redirect(url_for('task.manage_resources', task_id=task_id))
    
    return render_template('task/resources.html', task=task, project=project, form=form, resources=resource_users)

@task_bp.route('/resource/<int:resource_id>/delete', methods=['POST'])
@login_required
def delete_resource(resource_id):
    resource = TaskResource.query.get_or_404(resource_id)
    task = Task.query.get_or_404(resource.task_id)
    project = Project.query.get_or_404(task.project_id)
    
    # Check permissions
    if current_user.role == UserRole.TEAM_MEMBER:
        flash('You do not have permission to remove resources.', 'danger')
        return redirect(url_for('task.view', task_id=task.id))
    
    if current_user.role == UserRole.PROJECT_MANAGER and project.project_manager_id != current_user.id:
        flash('You can only manage resources for tasks in your own projects.', 'danger')
        return redirect(url_for('project.index'))
    
    try:
        db.session.delete(resource)
        db.session.commit()
        flash('Resource removed successfully', 'success')
    except Exception as e:
        db.session.rollback()
        flash(f'Error removing resource: {str(e)}', 'danger')
    
    return redirect(url_for('task.manage_resources', task_id=task.id))

@task_bp.route('/gantt/<int:project_id>')
@login_required
def gantt_chart(project_id):
    project = Project.query.get_or_404(project_id)
    
    # Check permissions for project managers
    if current_user.role == UserRole.PROJECT_MANAGER and project.project_manager_id != current_user.id:
        flash('You do not have permission to view this project.', 'danger')
        return redirect(url_for('project.index'))
    
    # Get all tasks for the project
    tasks = Task.query.filter_by(project_id=project_id).all()
    
    # Prepare data for gantt chart
    gantt_data = []
    for task in tasks:
        # Get resources
        resources = TaskResource.query.filter_by(task_id=task.id).all()
        resource_names = []
        for resource in resources:
            user = User.query.get(resource.user_id)
            resource_names.append(user.get_full_name())
        
        # Get parent name if applicable
        parent_name = None
        if task.parent_id:
            parent = Task.query.get(task.parent_id)
            parent_name = parent.name
        
        task_data = {
            'id': task.id,
            'name': task.name,
            'start': task.start_date.strftime('%Y-%m-%d'),
            'end': task.end_date.strftime('%Y-%m-%d'),
            'progress': 100 if task.status == TaskStatus.COMPLETED else 
                        50 if task.status == TaskStatus.IN_PROGRESS else 
                        0,
            'dependencies': parent_name,
            'resources': ', '.join(resource_names),
            'status': task.status.value,
            'is_milestone': task.is_milestone
        }
        gantt_data.append(task_data)
    
    return render_template('task/gantt.html', project=project, tasks=gantt_data)

@task_bp.route('/schedule/<int:project_id>')
@login_required
def schedule_versions(project_id):
    project = Project.query.get_or_404(project_id)

    # Check permissions for project managers
    if current_user.role == UserRole.PROJECT_MANAGER and project.project_manager_id != current_user.id:
        flash('You do not have permission to view this project.', 'danger')
        return redirect(url_for('project.index'))

    # Get schedule versions
    versions = ScheduleVersion.query.filter_by(project_id=project_id).order_by(ScheduleVersion.created_at.desc()).all()

    return render_template('task/schedule_versions.html', project=project, versions=versions)
