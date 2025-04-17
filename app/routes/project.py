from flask import Blueprint, render_template, redirect, url_for, flash, request, current_app
from flask_login import login_required, current_user
from app import db
from app.models.user import User, UserRole
from app.models.project import Project, ProjectVersion, ProjectType, ProjectStatus, POAttachment, SOWAttachment
from app.forms.project_forms import ProjectForm, ProjectSearchForm, ProjectVersionForm
from werkzeug.utils import secure_filename
import os
import random
from datetime import datetime

project_bp = Blueprint('project', __name__, url_prefix='/projects')

@project_bp.route('/')
@login_required
def index():
    # Project list with search functionality
    form = ProjectSearchForm()
    
    # Populate project manager dropdown
    project_managers = User.query.filter_by(role=UserRole.PROJECT_MANAGER).all()
    form.project_manager_id.choices = [(0, 'All')] + [(pm.id, pm.get_full_name()) for pm in project_managers]
    
    # Get query parameters
    project_id = request.args.get('project_id', '')
    name = request.args.get('name', '')
    status = request.args.get('status', '')
    project_manager_id = request.args.get('project_manager_id', type=int)
    start_date_from = request.args.get('start_date_from', '')
    start_date_to = request.args.get('start_date_to', '')
    
    # Build query
    query = Project.query
    
    if project_id:
        query = query.filter(Project.project_id.like(f'%{project_id}%'))
    if name:
        query = query.filter(Project.name.like(f'%{name}%'))
    if status:
        query = query.filter(Project.status == ProjectStatus[status])
    if project_manager_id and project_manager_id > 0:
        query = query.filter(Project.project_manager_id == project_manager_id)
    if start_date_from:
        try:
            from_date = datetime.strptime(start_date_from, '%Y-%m-%d').date()
            query = query.filter(Project.start_date >= from_date)
        except ValueError:
            pass
    if start_date_to:
        try:
            to_date = datetime.strptime(start_date_to, '%Y-%m-%d').date()
            query = query.filter(Project.start_date <= to_date)
        except ValueError:
            pass
    
    # For project managers, show only their projects
    if current_user.role == UserRole.PROJECT_MANAGER:
        query = query.filter(Project.project_manager_id == current_user.id)
    
    # Paginate results
    page = request.args.get('page', 1, type=int)
    per_page = 10
    projects = query.order_by(Project.created_at.desc()).paginate(page=page, per_page=per_page)
    
    return render_template('project/index.html', projects=projects, form=form)

@project_bp.route('/create', methods=['GET', 'POST'])
@login_required
def create():
    # Only admins and project managers can create projects
    if current_user.role not in [UserRole.ADMIN, UserRole.PROJECT_MANAGER]:
        flash('You do not have permission to create projects.', 'danger')
        return redirect(url_for('project.index'))
    
    form = ProjectForm()
    
    # Populate project manager dropdown
    project_managers = User.query.filter_by(role=UserRole.PROJECT_MANAGER).all()
    form.project_manager_id.choices = [(pm.id, pm.get_full_name()) for pm in project_managers]
    
    # For project managers, default to themselves and disable field
    if current_user.role == UserRole.PROJECT_MANAGER:
        form.project_manager_id.data = current_user.id
    
    if form.validate_on_submit():
        try:
            # Create new project
            project = Project(
                name=form.name.data,
                description=form.description.data,
                start_date=form.start_date.data,
                end_date=form.end_date.data,
                project_type=ProjectType[form.project_type.data],
                project_manager_id=form.project_manager_id.data,
                customer_po_number=form.customer_po_number.data,
                status=ProjectStatus[form.status.data]
            )
            
            # Set amount fields based on project type
            if project.project_type == ProjectType.FIXED_PRICE:
                project.total_amount = form.total_amount.data
            else:  # T&M_PRICE
                project.monthly_billing = form.monthly_billing.data
            
            # Generate 5-digit project ID
            while True:
                project_id = str(random.randint(10000, 99999))
                if not Project.query.filter_by(project_id=project_id).first():
                    break
            
            project.project_id = project_id
            
            db.session.add(project)
            db.session.commit()
            
            # Create initial project version
            initial_version = ProjectVersion(
                project_id=project.id,
                version="1.0",
                changes="Initial project creation",
                created_by=current_user.id
            )
            db.session.add(initial_version)
            
            # Handle file uploads
            if form.po_attachment.data:
                filename = secure_filename(form.po_attachment.data.filename)
                upload_folder = os.path.join(current_app.root_path, 'static/uploads/po')
                os.makedirs(upload_folder, exist_ok=True)
                filepath = os.path.join(upload_folder, f"{project.project_id}_{filename}")
                form.po_attachment.data.save(filepath)
                
                po_attachment = POAttachment(
                    project_id=project.id,
                    filename=filename,
                    file_path=f"uploads/po/{project.project_id}_{filename}",
                    uploaded_by=current_user.id
                )
                db.session.add(po_attachment)
            
            if form.sow_attachment.data:
                filename = secure_filename(form.sow_attachment.data.filename)
                upload_folder = os.path.join(current_app.root_path, 'static/uploads/sow')
                os.makedirs(upload_folder, exist_ok=True)
                filepath = os.path.join(upload_folder, f"{project.project_id}_{filename}")
                form.sow_attachment.data.save(filepath)
                
                sow_attachment = SOWAttachment(
                    project_id=project.id,
                    filename=filename,
                    file_path=f"uploads/sow/{project.project_id}_{filename}",
                    uploaded_by=current_user.id
                )
                db.session.add(sow_attachment)
            
            db.session.commit()
            
            flash(f'Project "{project.name}" has been created with ID: {project.project_id}', 'success')
            return redirect(url_for('project.view', project_id=project.id))
            
        except Exception as e:
            db.session.rollback()
            flash(f'Error creating project: {str(e)}', 'danger')
    
    return render_template('project/create.html', form=form)

@project_bp.route('/<int:project_id>')
@login_required
def view(project_id):
    project = Project.query.get_or_404(project_id)
    
    # Check permissions for project managers
    if current_user.role == UserRole.PROJECT_MANAGER and project.project_manager_id != current_user.id:
        flash('You do not have permission to view this project.', 'danger')
        return redirect(url_for('project.index'))
    
    # Get attachments
    po_attachments = POAttachment.query.filter_by(project_id=project.id).all()
    sow_attachments = SOWAttachment.query.filter_by(project_id=project.id).all()
    
    # Get project manager name
    project_manager = User.query.get(project.project_manager_id)
    
    # Get project versions
    versions = ProjectVersion.query.filter_by(project_id=project.id).order_by(ProjectVersion.created_at.desc()).all()
    
    return render_template(
        'project/view.html',
        project=project,
        project_manager=project_manager,
        po_attachments=po_attachments,
        sow_attachments=sow_attachments,
        versions=versions
    )

@project_bp.route('/<int:project_id>/edit', methods=['GET', 'POST'])
@login_required
def edit(project_id):
    project = Project.query.get_or_404(project_id)
    
    # Check permissions
    if current_user.role == UserRole.TEAM_MEMBER:
        flash('You do not have permission to edit projects.', 'danger')
        return redirect(url_for('project.view', project_id=project.id))
    
    if current_user.role == UserRole.PROJECT_MANAGER and project.project_manager_id != current_user.id:
        flash('You can only edit your own projects.', 'danger')
        return redirect(url_for('project.index'))
    
    form = ProjectForm(obj=project)
    
    # Populate project manager dropdown
    project_managers = User.query
    





    ####
    # Populate project manager dropdown (continued from previous)
    project_managers = User.query.filter_by(role=UserRole.PROJECT_MANAGER).all()
    form.project_manager_id.choices = [(pm.id, pm.get_full_name()) for pm in project_managers]
    
    # For project managers, default to themselves and disable field
    if current_user.role == UserRole.PROJECT_MANAGER:
        form.project_manager_id.data = current_user.id
    
    # Convert enum values to form values
    form.project_type.data = project.project_type.name
    form.status.data = project.status.name
    
    if form.validate_on_submit():
        try:
            old_data = {
                'name': project.name,
                'description': project.description,
                'start_date': project.start_date,
                'end_date': project.end_date,
                'project_type': project.project_type,
                'total_amount': project.total_amount,
                'monthly_billing': project.monthly_billing,
                'project_manager_id': project.project_manager_id,
                'customer_po_number': project.customer_po_number,
                'status': project.status
            }
            
            # Update project data
            project.name = form.name.data
            project.description = form.description.data
            project.start_date = form.start_date.data
            project.end_date = form.end_date.data
            project.project_type = ProjectType[form.project_type.data]
            
            # Admin can change project manager
            if current_user.role == UserRole.ADMIN:
                project.project_manager_id = form.project_manager_id.data
            
            project.customer_po_number = form.customer_po_number.data
            project.status = ProjectStatus[form.status.data]
            
            # Update amount fields based on project type
            if project.project_type == ProjectType.FIXED_PRICE:
                project.total_amount = form.total_amount.data
                project.monthly_billing = None
            else:  # T&M_PRICE
                project.monthly_billing = form.monthly_billing.data
                project.total_amount = None
            
            # Check if there were significant changes to create a new version
            has_changes = False
            changes_description = []
            
            if project.name != old_data['name']:
                changes_description.append(f"Name changed from '{old_data['name']}' to '{project.name}'")
                has_changes = True
            if project.description != old_data['description']:
                changes_description.append("Description updated")
                has_changes = True
            if project.start_date != old_data['start_date']:
                changes_description.append(f"Start date changed from {old_data['start_date']} to {project.start_date}")
                has_changes = True
            if project.end_date != old_data['end_date']:
                changes_description.append(f"End date changed from {old_data['end_date']} to {project.end_date}")
                has_changes = True
            if project.project_type != old_data['project_type']:
                changes_description.append(f"Project type changed from {old_data['project_type'].value} to {project.project_type.value}")
                has_changes = True
            if project.status != old_data['status']:
                changes_description.append(f"Status changed from {old_data['status'].value} to {project.status.value}")
                has_changes = True
            if project.project_manager_id != old_data['project_manager_id']:
                old_pm = User.query.get(old_data['project_manager_id']).get_full_name()
                new_pm = User.query.get(project.project_manager_id).get_full_name()
                changes_description.append(f"Project manager changed from {old_pm} to {new_pm}")
                has_changes = True
            
            # Create new version if significant changes occurred
            if has_changes:
                # Get latest version
                latest_version = ProjectVersion.query.filter_by(project_id=project.id).order_by(
                    ProjectVersion.version.desc()).first()
                
                # Parse version number and increment
                major, minor = latest_version.version.split('.')
                new_version = f"{major}.{int(minor) + 1}"
                
                # Create new version record
                project_version = ProjectVersion(
                    project_id=project.id,
                    version=new_version,
                    changes="\n".join(changes_description),
                    created_by=current_user.id
                )
                db.session.add(project_version)
            
            # Handle file uploads
            if form.po_attachment.data:
                filename = secure_filename(form.po_attachment.data.filename)
                upload_folder = os.path.join(current_app.root_path, 'static/uploads/po')
                os.makedirs(upload_folder, exist_ok=True)
                filepath = os.path.join(upload_folder, f"{project.project_id}_{filename}")
                form.po_attachment.data.save(filepath)
                
                po_attachment = POAttachment(
                    project_id=project.id,
                    filename=filename,
                    file_path=f"uploads/po/{project.project_id}_{filename}",
                    uploaded_by=current_user.id
                )
                db.session.add(po_attachment)
            
            if form.sow_attachment.data:
                filename = secure_filename(form.sow_attachment.data.filename)
                upload_folder = os.path.join(current_app.root_path, 'static/uploads/sow')
                os.makedirs(upload_folder, exist_ok=True)
                filepath = os.path.join(upload_folder, f"{project.project_id}_{filename}")
                form.sow_attachment.data.save(filepath)
                
                sow_attachment = SOWAttachment(
                    project_id=project.id,
                    filename=filename,
                    file_path=f"uploads/sow/{project.project_id}_{filename}",
                    uploaded_by=current_user.id
                )
                db.session.add(sow_attachment)
            
            db.session.commit()
            
            flash(f'Project "{project.name}" has been updated', 'success')
            return redirect(url_for('project.view', project_id=project.id))
            
        except Exception as e:
            db.session.rollback()
            flash(f'Error updating project: {str(e)}', 'danger')
    
    return render_template('project/edit.html', form=form, project=project)

@project_bp.route('/<int:project_id>/version', methods=['GET', 'POST'])
@login_required
def new_version(project_id):
    project = Project.query.get_or_404(project_id)
    
    # Check permissions
    if current_user.role == UserRole.TEAM_MEMBER:
        flash('You do not have permission to create new project versions.', 'danger')
        return redirect(url_for('project.view', project_id=project.id))
    
    if current_user.role == UserRole.PROJECT_MANAGER and project.project_manager_id != current_user.id:
        flash('You can only edit your own projects.', 'danger')
        return redirect(url_for('project.index'))
    
    form = ProjectVersionForm()
    
    if form.validate_on_submit():
        # Get latest version
        latest_version = ProjectVersion.query.filter_by(project_id=project.id).order_by(
            ProjectVersion.version.desc()).first()
        
        # Parse version number and increment
        major, minor = latest_version.version.split('.')
        new_version = f"{major}.{int(minor) + 1}"
        
        # Create new version record
        project_version = ProjectVersion(
            project_id=project.id,
            version=new_version,
            changes=form.changes.data,
            created_by=current_user.id
        )
        db.session.add(project_version)
        db.session.commit()
        
        flash(f'New project version {new_version} has been created', 'success')
        return redirect(url_for('project.view', project_id=project.id))
    
    return render_template('project/new_version.html', form=form, project=project)

@project_bp.route('/<int:project_id>/versions')
@login_required
def versions(project_id):
    project = Project.query.get_or_404(project_id)
    
    # Check permissions for project managers
    if current_user.role == UserRole.PROJECT_MANAGER and project.project_manager_id != current_user.id:
        flash('You do not have permission to view this project.', 'danger')
        return redirect(url_for('project.index'))
    
    # Get project versions
    versions = ProjectVersion.query.filter_by(project_id=project.id).order_by(ProjectVersion.created_at.desc()).all()
    
    return render_template('project/versions.html', project=project, versions=versions)

@project_bp.route('/<int:project_id>/delete', methods=['POST'])
@login_required
def delete(project_id):
    # Only admins can delete projects
    if current_user.role != UserRole.ADMIN:
        flash('You do not have permission to delete projects.', 'danger')
        return redirect(url_for('project.index'))
    
    project = Project.query.get_or_404(project_id)
    
    try:
        db.session.delete(project)
        db.session.commit()
        flash(f'Project "{project.name}" has been deleted', 'success')
    except Exception as e:
        db.session.rollback()
        flash(f'Error deleting project: {str(e)}', 'danger')
    
    return redirect(url_for('project.index'))