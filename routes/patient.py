"""
患者端接口
"""
from flask import Blueprint, request, jsonify
from models import db, Patient, Task, Submission, Comment
from auth import token_required

patient_bp = Blueprint('patient', __name__)


@patient_bp.route('/tasks', methods=['GET'])
@token_required(roles=['patient', 'admin'])
def get_my_tasks():
    """获取我的任务"""
    patient_id = request.user['user_id']
    patient = Patient.query.get(patient_id)
    if not patient:
        return jsonify({'success': False, 'error': '患者不存在'}), 404

    tasks = Task.query.filter(
        Task.doctor_id == patient.doctor_id,
        db.or_(Task.target_patient_id == None, Task.target_patient_id == patient_id)
    ).order_by(Task.created_at.desc()).all()

    result = []
    for t in tasks:
        task_dict = t.to_dict()
        sub = Submission.query.filter_by(task_id=t.id, patient_id=patient_id).first()
        task_dict['submitted'] = sub is not None
        result.append(task_dict)

    return jsonify({'success': True, 'tasks': result})


@patient_bp.route('/submit', methods=['POST'])
@token_required(roles=['patient', 'admin'])
def submit_training():
    """提交训练结果"""
    data = request.get_json()
    patient_id = request.user['user_id']

    submission = Submission(
        task_id=data.get('task_id'),
        patient_id=patient_id,
        type=data.get('type'),
        text=data.get('text'),
        speed=data.get('speed'),
        words=data.get('words'),
        duration=data.get('duration'),
        discrim_score=data.get('discrim_score'),
        discrim_total=data.get('discrim_total'),
        discrim_rate=data.get('discrim_rate'),
        device_info=data.get('device_info')
    )
    db.session.add(submission)
    db.session.commit()

    return jsonify({'success': True, 'submission': submission.to_dict()})


@patient_bp.route('/history', methods=['GET'])
@token_required(roles=['patient', 'admin'])
def get_history():
    """获取历史训练记录"""
    patient_id = request.user['user_id']
    submissions = Submission.query.filter_by(patient_id=patient_id).order_by(
        Submission.submitted_at.desc()).limit(200).all()
    return jsonify({'success': True, 'history': [s.to_dict() for s in submissions]})


@patient_bp.route('/comment', methods=['GET'])
@token_required(roles=['patient', 'admin'])
def get_my_comment():
    """获取医生对我的指导"""
    patient_id = request.user['user_id']
    comment = Comment.query.filter_by(patient_id=patient_id).first()
    if not comment:
        return jsonify({'success': True, 'comment': None})
    return jsonify({'success': True, 'comment': comment.to_dict()})
