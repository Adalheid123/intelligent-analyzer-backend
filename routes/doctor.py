"""
医生端接口
"""
from flask import Blueprint, request, jsonify
from models import db, Doctor, Patient, Task, Submission, Comment
from auth import token_required

doctor_bp = Blueprint('doctor', __name__)


@doctor_bp.route('/patients', methods=['GET'])
@token_required(roles=['doctor', 'admin'])
def get_patients():
    """获取当前医生的患者列表"""
    doctor_id = request.user['user_id']
    patients = Patient.query.filter_by(doctor_id=doctor_id).all()
    return jsonify({'success': True, 'patients': [p.to_dict() for p in patients]})


@doctor_bp.route('/patients', methods=['POST'])
@token_required(roles=['doctor', 'admin'])
def add_patient():
    """添加患者"""
    data = request.get_json()
    doctor_id = request.user['user_id']

    hospital = data.get('hospital', '').strip()
    name = data.get('name', '').strip()
    password = data.get('password', '123456')
    age = data.get('age')
    gender = data.get('gender')
    diagnosis = data.get('diagnosis')
    hearing_level = data.get('hearing_level')

    if not hospital or not name:
        return jsonify({'success': False, 'error': '医院和姓名不能为空'}), 400

    exist = Patient.query.filter_by(hospital=hospital, doctor_id=doctor_id, name=name).first()
    if exist:
        return jsonify({'success': False, 'error': '该患者已存在'}), 400

    patient = Patient(
        hospital=hospital,
        doctor_id=doctor_id,
        name=name,
        age=age,
        gender=gender,
        diagnosis=diagnosis,
        hearing_level=hearing_level
    )
    patient.set_password(password)
    db.session.add(patient)
    db.session.commit()

    return jsonify({'success': True, 'patient': patient.to_dict()})


@doctor_bp.route('/patients/<patient_id>', methods=['PUT'])
@token_required(roles=['doctor', 'admin'])
def update_patient(patient_id):
    """更新患者信息"""
    data = request.get_json()
    patient = Patient.query.get(patient_id)
    if not patient:
        return jsonify({'success': False, 'error': '患者不存在'}), 404

    if 'age' in data:
        patient.age = data['age']
    if 'gender' in data:
        patient.gender = data['gender']
    if 'diagnosis' in data:
        patient.diagnosis = data['diagnosis']
    if 'hearing_level' in data:
        patient.hearing_level = data['hearing_level']
    if 'rehab_advice' in data:
        patient.rehab_advice = data['rehab_advice']

    db.session.commit()
    return jsonify({'success': True, 'patient': patient.to_dict(include_advice=True)})


@doctor_bp.route('/patients/<patient_id>', methods=['DELETE'])
@token_required(roles=['doctor', 'admin'])
def delete_patient(patient_id):
    """移除患者"""
    patient = Patient.query.get(patient_id)
    if not patient:
        return jsonify({'success': False, 'error': '患者不存在'}), 404

    db.session.delete(patient)
    db.session.commit()
    return jsonify({'success': True})


@doctor_bp.route('/tasks', methods=['GET'])
@token_required(roles=['doctor', 'admin'])
def get_tasks():
    """获取当前医生的任务列表"""
    doctor_id = request.user['user_id']
    tasks = Task.query.filter_by(doctor_id=doctor_id).order_by(Task.created_at.desc()).all()
    return jsonify({'success': True, 'tasks': [t.to_dict() for t in tasks]})


@doctor_bp.route('/tasks', methods=['POST'])
@token_required(roles=['doctor', 'admin'])
def publish_task():
    """发布任务"""
    data = request.get_json()
    doctor_id = request.user['user_id']

    title = data.get('title', '').strip()
    task_type = data.get('type', 'reading')
    requirement = data.get('requirement', '').strip()
    deadline = data.get('deadline')
    target = data.get('target')

    if not title or not requirement:
        return jsonify({'success': False, 'error': '标题和说明不能为空'}), 400

    target_patient_id = None if target == 'all' else target

    task = Task(
        doctor_id=doctor_id,
        target_patient_id=target_patient_id,
        title=title,
        type=task_type,
        requirement=requirement,
        deadline=deadline
    )
    db.session.add(task)
    db.session.commit()

    return jsonify({'success': True, 'task': task.to_dict()})


@doctor_bp.route('/tasks/<task_id>', methods=['DELETE'])
@token_required(roles=['doctor', 'admin'])
def delete_task(task_id):
    """删除任务"""
    task = Task.query.get(task_id)
    if not task:
        return jsonify({'success': False, 'error': '任务不存在'}), 404

    db.session.delete(task)
    db.session.commit()
    return jsonify({'success': True})


@doctor_bp.route('/submissions', methods=['GET'])
@token_required(roles=['doctor', 'admin'])
def get_submissions():
    """获取提交记录"""
    doctor_id = request.user['user_id']
    task_id = request.args.get('task_id')

    query = Submission.query.join(Patient).filter(Patient.doctor_id == doctor_id)
    if task_id:
        query = query.filter(Submission.task_id == task_id)

    submissions = query.order_by(Submission.submitted_at.desc()).all()
    return jsonify({'success': True, 'submissions': [s.to_dict() for s in submissions]})


@doctor_bp.route('/comment', methods=['POST'])
@token_required(roles=['doctor', 'admin'])
def save_comment():
    """保存康复指导"""
    data = request.get_json()
    doctor_id = request.user['user_id']
    patient_id = data.get('patient_id')
    content = data.get('content', '').strip()

    if not patient_id:
        return jsonify({'success': False, 'error': '缺少患者ID'}), 400

    comment = Comment.query.filter_by(patient_id=patient_id, doctor_id=doctor_id).first()
    if comment:
        comment.content = content
    else:
        comment = Comment(patient_id=patient_id, doctor_id=doctor_id, content=content)
        db.session.add(comment)

    db.session.commit()
    return jsonify({'success': True, 'comment': comment.to_dict()})
