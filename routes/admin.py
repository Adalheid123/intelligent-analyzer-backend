"""
管理后台接口（老师用）
"""
from flask import Blueprint, request, jsonify, send_file
from models import db, Doctor, Patient, Task, Submission, Comment
from auth import token_required
from io import BytesIO
from openpyxl import Workbook
from datetime import datetime

admin_bp = Blueprint('admin', __name__)


@admin_bp.route('/patients', methods=['GET'])
@token_required(roles=['admin'])
def get_all_patients():
    """获取所有患者"""
    hospital = request.args.get('hospital')
    doctor_id = request.args.get('doctor_id')

    query = Patient.query
    if hospital:
        query = query.filter_by(hospital=hospital)
    if doctor_id:
        query = query.filter_by(doctor_id=doctor_id)

    patients = query.order_by(Patient.created_at.desc()).all()
    return jsonify({'success': True, 'patients': [p.to_dict(include_advice=True) for p in patients]})


@admin_bp.route('/patient/<patient_id>', methods=['GET'])
@token_required(roles=['admin'])
def get_patient_detail(patient_id):
    """获取单个患者的完整数据"""
    patient = Patient.query.get(patient_id)
    if not patient:
        return jsonify({'success': False, 'error': '患者不存在'}), 404

    submissions = Submission.query.filter_by(patient_id=patient_id).order_by(
        Submission.submitted_at.desc()).all()
    comment = Comment.query.filter_by(patient_id=patient_id).first()

    return jsonify({
        'success': True,
        'patient': patient.to_dict(include_advice=True),
        'submissions': [s.to_dict() for s in submissions],
        'comment': comment.to_dict() if comment else None
    })


@admin_bp.route('/submissions', methods=['GET'])
@token_required(roles=['admin'])
def get_all_submissions():
    """获取所有提交记录"""
    patient_id = request.args.get('patient_id')
    query = Submission.query
    if patient_id:
        query = query.filter_by(patient_id=patient_id)
    submissions = query.order_by(Submission.submitted_at.desc()).limit(1000).all()
    return jsonify({'success': True, 'submissions': [s.to_dict() for s in submissions]})


@admin_bp.route('/stats', methods=['GET'])
@token_required(roles=['admin'])
def get_stats():
    """获取统计数据"""
    total_patients = Patient.query.count()
    total_doctors = Doctor.query.count()
    total_submissions = Submission.query.count()
    total_tasks = Task.query.count()

    return jsonify({
        'success': True,
        'stats': {
            'total_patients': total_patients,
            'total_doctors': total_doctors,
            'total_submissions': total_submissions,
            'total_tasks': total_tasks
        }
    })


@admin_bp.route('/export/all', methods=['GET'])
@token_required(roles=['admin'])
def export_all():
    """导出全部数据为 Excel"""
    wb = Workbook()
    ws = wb.active
    ws.title = "训练数据"

    headers = ['患者姓名', '年龄', '性别', '诊断类型', '听力等级', '医院', '任务标题',
               '任务类型', '朗读内容', '语速(字/分钟)', '字数', '时长(秒)',
               '辨听得分', '辨听总数', '辨听正确率', '提交时间']
    ws.append(headers)

    submissions = Submission.query.order_by(Submission.submitted_at.desc()).all()
    for s in submissions:
        patient = Patient.query.get(s.patient_id)
        task = Task.query.get(s.task_id) if s.task_id else None
        ws.append([
            patient.name if patient else '',
            patient.age if patient else '',
            patient.gender if patient else '',
            patient.diagnosis if patient else '',
            patient.hearing_level if patient else '',
            patient.hospital if patient else '',
            task.title if task else '',
            task.type if task else '',
            s.text or '',
            s.speed or '',
            s.words or '',
            s.duration or '',
            s.discrim_score or '',
            s.discrim_total or '',
            s.discrim_rate or '',
            s.submitted_at.strftime('%Y-%m-%d %H:%M:%S') if s.submitted_at else ''
        ])

    output = BytesIO()
    wb.save(output)
    output.seek(0)

    filename = f'康复数据_全部_{datetime.now().strftime("%Y%m%d_%H%M%S")}.xlsx'
    return send_file(output, mimetype='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',
                     as_attachment=True, download_name=filename)


@admin_bp.route('/export/patient/<patient_id>', methods=['GET'])
@token_required(roles=['admin'])
def export_patient(patient_id):
    """导出单个患者数据"""
    patient = Patient.query.get(patient_id)
    if not patient:
        return jsonify({'success': False, 'error': '患者不存在'}), 404

    wb = Workbook()
    ws = wb.active
    ws.title = "患者数据"

    ws.append(['姓名', patient.name])
    ws.append(['年龄', patient.age])
    ws.append(['性别', patient.gender])
    ws.append(['诊断类型', patient.diagnosis])
    ws.append(['听力等级', patient.hearing_level])
    ws.append(['医院', patient.hospital])
    ws.append([])
    ws.append(['任务标题', '任务类型', '朗读内容', '语速', '字数', '时长',
               '辨听得分', '辨听总数', '辨听正确率', '提交时间'])

    submissions = Submission.query.filter_by(patient_id=patient_id).order_by(
        Submission.submitted_at.desc()).all()
    for s in submissions:
        task = Task.query.get(s.task_id) if s.task_id else None
        ws.append([
            task.title if task else '',
            task.type if task else '',
            s.text or '',
            s.speed or '',
            s.words or '',
            s.duration or '',
            s.discrim_score or '',
            s.discrim_total or '',
            s.discrim_rate or '',
            s.submitted_at.strftime('%Y-%m-%d %H:%M:%S') if s.submitted_at else ''
        ])

    output = BytesIO()
    wb.save(output)
    output.seek(0)

    filename = f'康复数据_{patient.name}_{datetime.now().strftime("%Y%m%d")}.xlsx'
    return send_file(output, mimetype='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',
                     as_attachment=True, download_name=filename)
