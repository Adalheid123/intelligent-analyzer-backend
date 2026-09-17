"""
管理后台接口（多医院管理员支持）
"""
from flask import Blueprint, request, jsonify, send_file
from models import db, Doctor, Patient, Task, Submission, Comment, Admin
from auth import token_required, generate_token
from io import BytesIO
from openpyxl import Workbook, load_workbook
from datetime import datetime
from werkzeug.security import generate_password_hash

admin_bp = Blueprint('admin', __name__)

DEFAULT_PASSWORD = '123456'


# ============================================================
# 辅助：按 scope 过滤
# ============================================================
def _apply_scope_filter(query, model):
    """根据当前管理员 scope 过滤查询"""
    user = getattr(request, 'user', None)
    if not user:
        return query
    scope = user.get('scope', 'hospital')
    hospital = user.get('hospital')
    if scope == 'global':
        return query
    if hospital and hasattr(model, 'hospital'):
        return query.filter(model.hospital == hospital)
    return query.filter(db.false())


# ============================================================
# 管理员登录
# ============================================================
@admin_bp.route('/login', methods=['POST'])
def admin_login():
    data = request.get_json() or {}
    username = data.get('username', '').strip()
    password = data.get('password', '')

    admin = Admin.query.filter_by(username=username).first()
    if not admin or not admin.check_password(password):
        return jsonify({'success': False, 'error': '账号或密码错误'}), 401

    token = generate_token(
        admin.id, 'admin',
        {'username': admin.username, 'scope': admin.scope, 'hospital': admin.hospital}
    )
    return jsonify({'success': True, 'token': token, 'user': admin.to_dict()})


# ============================================================
# 患者管理
# ============================================================
@admin_bp.route('/patients', methods=['GET'])
@token_required(roles=['admin'])
def get_all_patients():
    hospital = request.args.get('hospital')
    doctor_id = request.args.get('doctor_id')

    query = Patient.query
    query = _apply_scope_filter(query, Patient)
    if hospital:
        query = query.filter_by(hospital=hospital)
    if doctor_id:
        query = query.filter_by(doctor_id=doctor_id)

    patients = query.order_by(Patient.created_at.desc()).all()
    return jsonify({'success': True, 'patients': [p.to_dict(include_advice=True) for p in patients]})


@admin_bp.route('/patient/<patient_id>', methods=['GET'])
@token_required(roles=['admin'])
def get_patient_detail(patient_id):
    patient = Patient.query.get(patient_id)
    if not patient:
        return jsonify({'success': False, 'error': '患者不存在'}), 404

    scope = request.user.get('scope')
    hospital = request.user.get('hospital')
    if scope != 'global' and patient.hospital != hospital:
        return jsonify({'success': False, 'error': '无权访问该患者'}), 403

    submissions = Submission.query.filter_by(patient_id=patient_id).order_by(
        Submission.submitted_at.desc()).all()
    comment = Comment.query.filter_by(patient_id=patient_id).first()

    return jsonify({
        'success': True,
        'patient': patient.to_dict(include_advice=True),
        'submissions': [s.to_dict() for s in submissions],
        'comment': comment.to_dict() if comment else None
    })


# ============================================================
# 医生管理
# ============================================================
@admin_bp.route('/doctors', methods=['GET'])
@token_required(roles=['admin'])
def get_all_doctors():
    query = Doctor.query
    query = _apply_scope_filter(query, Doctor)
    doctors = query.order_by(Doctor.created_at.desc()).all()

    result = []
    for d in doctors:
        item = d.to_dict()
        item['patient_count'] = Patient.query.filter_by(doctor_id=d.id).count()
        result.append(item)
    return jsonify({'success': True, 'doctors': result})


# ============================================================
# 提交记录
# ============================================================
@admin_bp.route('/submissions', methods=['GET'])
@token_required(roles=['admin'])
def get_all_submissions():
    patient_id = request.args.get('patient_id')
    query = Submission.query

    scope = request.user.get('scope')
    hospital = request.user.get('hospital')
    if scope != 'global' and hospital:
        query = query.join(Patient).filter(Patient.hospital == hospital)

    if patient_id:
        query = query.filter(Submission.patient_id == patient_id)

    submissions = query.order_by(Submission.submitted_at.desc()).limit(1000).all()
    return jsonify({'success': True, 'submissions': [s.to_dict() for s in submissions]})


# ============================================================
# 统计
# ============================================================
@admin_bp.route('/stats', methods=['GET'])
@token_required(roles=['admin'])
def get_stats():
    scope = request.user.get('scope')
    hospital = request.user.get('hospital')

    if scope == 'global':
        total_patients = Patient.query.count()
        total_doctors = Doctor.query.count()
        total_submissions = Submission.query.count()
        total_tasks = Task.query.count()
        total_hospitals = db.session.query(Patient.hospital).distinct().count()
    else:
        total_patients = Patient.query.filter_by(hospital=hospital).count()
        total_doctors = Doctor.query.filter_by(hospital=hospital).count()
        total_submissions = Submission.query.join(Patient).filter(Patient.hospital == hospital).count()
        total_tasks = Task.query.join(Doctor).filter(Doctor.hospital == hospital).count()
        total_hospitals = 1

    return jsonify({
        'success': True,
        'stats': {
            'total_patients': total_patients,
            'total_doctors': total_doctors,
            'total_submissions': total_submissions,
            'total_tasks': total_tasks,
            'total_hospitals': total_hospitals,
            'scope': scope,
            'hospital': hospital
        }
    })


# ============================================================
# 批量导入：医生
# ============================================================
@admin_bp.route('/import/doctors', methods=['POST'])
@token_required(roles=['admin'])
def import_doctors():
    """Excel 列：医院 | 医生姓名（密码统一 123456）"""
    if 'file' not in request.files:
        return jsonify({'success': False, 'error': '没有上传文件'}), 400
    file = request.files['file']
    if not file.filename.lower().endswith(('.xlsx', '.xls')):
        return jsonify({'success': False, 'error': '只支持 .xlsx / .xls'}), 400

    scope = request.user.get('scope')
    my_hospital = request.user.get('hospital')

    try:
        wb = load_workbook(BytesIO(file.read()))
        sheet = wb.active
        created, skipped, errors = 0, 0, []

        for idx, row in enumerate(sheet.iter_rows(min_row=2, values_only=True), start=2):
            if not row or not row[0] or not row[1]:
                continue
            hospital = str(row[0]).strip()
            name = str(row[1]).strip()

            if scope != 'global' and hospital != my_hospital:
                errors.append(f'第{idx}行：无权导入其他医院（{hospital}）')
                continue

            exist = Doctor.query.filter_by(hospital=hospital, name=name).first()
            if exist:
                skipped += 1
                continue

            doctor = Doctor(hospital=hospital, name=name)
            doctor.set_password(DEFAULT_PASSWORD)
            db.session.add(doctor)
            created += 1

        db.session.commit()
        return jsonify({
            'success': True,
            'created': created,
            'skipped': skipped,
            'errors': errors
        })
    except Exception as e:
        db.session.rollback()
        return jsonify({'success': False, 'error': str(e)}), 500


# ============================================================
# 批量导入：患者
# ============================================================
@admin_bp.route('/import/patients', methods=['POST'])
@token_required(roles=['admin'])
def import_patients():
    """Excel 列：医院 | 主治医生 | 姓名 | 年龄 | 性别 | 诊断 | 听力等级（密码统一 123456）"""
    if 'file' not in request.files:
        return jsonify({'success': False, 'error': '没有上传文件'}), 400
    file = request.files['file']
    if not file.filename.lower().endswith(('.xlsx', '.xls')):
        return jsonify({'success': False, 'error': '只支持 .xlsx / .xls'}), 400

    scope = request.user.get('scope')
    my_hospital = request.user.get('hospital')

    try:
        wb = load_workbook(BytesIO(file.read()))
        sheet = wb.active
        created, skipped, errors = 0, 0, []

        for idx, row in enumerate(sheet.iter_rows(min_row=2, values_only=True), start=2):
            if not row or len(row) < 3 or not row[0] or not row[1] or not row[2]:
                continue
            hospital = str(row[0]).strip()
            doctor_name = str(row[1]).strip()
            patient_name = str(row[2]).strip()
            age = row[3] if len(row) > 3 else None
            gender = str(row[4]).strip() if len(row) > 4 and row[4] else None
            diagnosis = str(row[5]).strip() if len(row) > 5 and row[5] else None
            hearing_level = str(row[6]).strip() if len(row) > 6 and row[6] else None

            if scope != 'global' and hospital != my_hospital:
                errors.append(f'第{idx}行：无权导入其他医院（{hospital}）')
                continue

            doctor = Doctor.query.filter_by(hospital=hospital, name=doctor_name).first()
            if not doctor:
                errors.append(f'第{idx}行：医生不存在（{hospital} / {doctor_name}）')
                continue

            exist = Patient.query.filter_by(hospital=hospital, doctor_id=doctor.id, name=patient_name).first()
            if exist:
                skipped += 1
                continue

            patient = Patient(
                hospital=hospital,
                doctor_id=doctor.id,
                name=patient_name,
                age=int(age) if age else None,
                gender=gender,
                diagnosis=diagnosis,
                hearing_level=hearing_level
            )
            patient.set_password(DEFAULT_PASSWORD)
            db.session.add(patient)
            created += 1

        db.session.commit()
        return jsonify({
            'success': True,
            'created': created,
            'skipped': skipped,
            'errors': errors
        })
    except Exception as e:
        db.session.rollback()
        return jsonify({'success': False, 'error': str(e)}), 500


# ============================================================
# 医院管理（仅超管）
# ============================================================
@admin_bp.route('/hospitals', methods=['GET'])
@token_required(roles=['admin'])
def list_hospitals():
    if request.user.get('scope') != 'global':
        return jsonify({'success': False, 'error': '仅超级管理员可访问'}), 403

    rows = db.session.query(Doctor.hospital).distinct().all()
    hospitals = sorted([r[0] for r in rows if r[0]])

    result = []
    for h in hospitals:
        admins = Admin.query.filter_by(hospital=h).all()
        result.append({
            'hospital': h,
            'doctor_count': Doctor.query.filter_by(hospital=h).count(),
            'patient_count': Patient.query.filter_by(hospital=h).count(),
            'admins': [a.to_dict() for a in admins]
        })
    return jsonify({'success': True, 'hospitals': result})


@admin_bp.route('/admins', methods=['GET'])
@token_required(roles=['admin'])
def list_admins():
    if request.user.get('scope') != 'global':
        return jsonify({'success': False, 'error': '仅超级管理员可访问'}), 403
    admins = Admin.query.order_by(Admin.created_at.desc()).all()
    return jsonify({'success': True, 'admins': [a.to_dict() for a in admins]})


@admin_bp.route('/admins', methods=['POST'])
@token_required(roles=['admin'])
def create_admin():
    if request.user.get('scope') != 'global':
        return jsonify({'success': False, 'error': '仅超级管理员可访问'}), 403

    data = request.get_json() or {}
    username = data.get('username', '').strip()
    hospital = data.get('hospital', '').strip()
    password = data.get('password', DEFAULT_PASSWORD)

    if not username or not hospital:
        return jsonify({'success': False, 'error': '用户名和医院不能为空'}), 400
    if Admin.query.filter_by(username=username).first():
        return jsonify({'success': False, 'error': '用户名已存在'}), 400

    admin = Admin(username=username, hospital=hospital, scope='hospital')
    admin.set_password(password)
    db.session.add(admin)
    db.session.commit()
    return jsonify({'success': True, 'admin': admin.to_dict()})


@admin_bp.route('/admins/<admin_id>', methods=['DELETE'])
@token_required(roles=['admin'])
def delete_admin(admin_id):
    if request.user.get('scope') != 'global':
        return jsonify({'success': False, 'error': '仅超级管理员可访问'}), 403
    admin = Admin.query.get(admin_id)
    if not admin:
        return jsonify({'success': False, 'error': '管理员不存在'}), 404
    if admin.username == 'admin':
        return jsonify({'success': False, 'error': '不能删除超级管理员'}), 400
    db.session.delete(admin)
    db.session.commit()
    return jsonify({'success': True})


# ============================================================
# 导出
# ============================================================
@admin_bp.route('/export/all', methods=['GET'])
@token_required(roles=['admin'])
def export_all():
    scope = request.user.get('scope')
    hospital = request.user.get('hospital')

    wb = Workbook()
    ws = wb.active
    ws.title = "训练数据"

    headers = ['患者姓名', '年龄', '性别', '诊断类型', '听力等级', '医院', '任务标题',
               '任务类型', '朗读内容', '语速(字/分钟)', '字数', '时长(秒)',
               '辨听得分', '辨听总数', '辨听正确率', '提交时间']
    ws.append(headers)

    query = Submission.query
    if scope != 'global' and hospital:
        query = query.join(Patient).filter(Patient.hospital == hospital)
    submissions = query.order_by(Submission.submitted_at.desc()).all()

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

    scope_label = '全部' if scope == 'global' else hospital
    filename = f'康复数据_{scope_label}_{datetime.now().strftime("%Y%m%d_%H%M%S")}.xlsx'
    return send_file(output, mimetype='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',
                     as_attachment=True, download_name=filename)


@admin_bp.route('/export/patient/<patient_id>', methods=['GET'])
@token_required(roles=['admin'])
def export_patient(patient_id):
    patient = Patient.query.get(patient_id)
    if not patient:
        return jsonify({'success': False, 'error': '患者不存在'}), 404

    scope = request.user.get('scope')
    if scope != 'global' and patient.hospital != request.user.get('hospital'):
        return jsonify({'success': False, 'error': '无权访问'}), 403

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
