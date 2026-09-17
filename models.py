"""
统一数据库模型
"""
from datetime import datetime
from flask_sqlalchemy import SQLAlchemy
from werkzeug.security import generate_password_hash, check_password_hash
import uuid


db = SQLAlchemy()


def gen_uuid():
    return str(uuid.uuid4())


# ========== 康复端 ==========

class Doctor(db.Model):
    __tablename__ = 'rehab_doctors'
    id = db.Column(db.String(36), primary_key=True, default=gen_uuid)
    hospital = db.Column(db.String(128), nullable=False)
    name = db.Column(db.String(64), nullable=False)
    password_hash = db.Column(db.String(256), nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    patients = db.relationship('Patient', backref='doctor', lazy=True)
    tasks = db.relationship('Task', backref='doctor', lazy=True)

    def set_password(self, password):
        self.password_hash = generate_password_hash(password)

    def check_password(self, password):
        return check_password_hash(self.password_hash, password)

    def to_dict(self):
        return {
            'id': self.id,
            'hospital': self.hospital,
            'name': self.name,
            'created_at': self.created_at.isoformat() if self.created_at else None
        }


class Patient(db.Model):
    __tablename__ = 'rehab_patients'
    id = db.Column(db.String(36), primary_key=True, default=gen_uuid)
    hospital = db.Column(db.String(128), nullable=False)
    doctor_id = db.Column(db.String(36), db.ForeignKey('rehab_doctors.id'), nullable=False)
    name = db.Column(db.String(64), nullable=False)
    age = db.Column(db.Integer)
    gender = db.Column(db.String(8))
    diagnosis = db.Column(db.String(128))
    hearing_level = db.Column(db.String(64))
    rehab_advice = db.Column(db.Text)
    password_hash = db.Column(db.String(256), nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    submissions = db.relationship('Submission', backref='patient', lazy=True)
    comments = db.relationship('Comment', backref='patient', lazy=True)

    def set_password(self, password):
        self.password_hash = generate_password_hash(password)

    def check_password(self, password):
        return check_password_hash(self.password_hash, password)

    def to_dict(self, include_advice=False):
        data = {
            'id': self.id,
            'hospital': self.hospital,
            'doctor_id': self.doctor_id,
            'name': self.name,
            'age': self.age,
            'gender': self.gender,
            'diagnosis': self.diagnosis,
            'hearing_level': self.hearing_level,
            'created_at': self.created_at.isoformat() if self.created_at else None
        }
        if include_advice:
            data['rehab_advice'] = self.rehab_advice
        return data


class Task(db.Model):
    __tablename__ = 'rehab_tasks'
    id = db.Column(db.String(36), primary_key=True, default=gen_uuid)
    doctor_id = db.Column(db.String(36), db.ForeignKey('rehab_doctors.id'), nullable=False)
    target_patient_id = db.Column(db.String(36), db.ForeignKey('rehab_patients.id'), nullable=True)
    title = db.Column(db.String(256), nullable=False)
    type = db.Column(db.String(32), nullable=False)
    requirement = db.Column(db.Text)
    deadline = db.Column(db.String(32))
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    submissions = db.relationship('Submission', backref='task', lazy=True)

    def to_dict(self):
        return {
            'id': self.id,
            'doctor_id': self.doctor_id,
            'target_patient_id': self.target_patient_id,
            'title': self.title,
            'type': self.type,
            'requirement': self.requirement,
            'deadline': self.deadline,
            'created_at': self.created_at.isoformat() if self.created_at else None
        }


class Submission(db.Model):
    __tablename__ = 'rehab_submissions'
    id = db.Column(db.String(36), primary_key=True, default=gen_uuid)
    task_id = db.Column(db.String(36), db.ForeignKey('rehab_tasks.id'), nullable=True)
    patient_id = db.Column(db.String(36), db.ForeignKey('rehab_patients.id'), nullable=False)
    type = db.Column(db.String(32), nullable=False)
    text = db.Column(db.Text)
    speed = db.Column(db.Integer)
    words = db.Column(db.Integer)
    duration = db.Column(db.Float)
    discrim_score = db.Column(db.Integer)
    discrim_total = db.Column(db.Integer)
    discrim_rate = db.Column(db.Integer)
    device_info = db.Column(db.String(256))
    submitted_at = db.Column(db.DateTime, default=datetime.utcnow)

    def to_dict(self):
        return {
            'id': self.id,
            'task_id': self.task_id,
            'patient_id': self.patient_id,
            'type': self.type,
            'text': self.text,
            'speed': self.speed,
            'words': self.words,
            'duration': self.duration,
            'discrim_score': self.discrim_score,
            'discrim_total': self.discrim_total,
            'discrim_rate': self.discrim_rate,
            'device_info': self.device_info,
            'submitted_at': self.submitted_at.isoformat() if self.submitted_at else None
        }


class Comment(db.Model):
    __tablename__ = 'rehab_comments'
    id = db.Column(db.String(36), primary_key=True, default=gen_uuid)
    patient_id = db.Column(db.String(36), db.ForeignKey('rehab_patients.id'), nullable=False)
    doctor_id = db.Column(db.String(36), db.ForeignKey('rehab_doctors.id'), nullable=False)
    content = db.Column(db.Text)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    def to_dict(self):
        return {
            'id': self.id,
            'patient_id': self.patient_id,
            'doctor_id': self.doctor_id,
            'content': self.content,
            'updated_at': self.updated_at.isoformat() if self.updated_at else None
        }


class Admin(db.Model):
    __tablename__ = 'rehab_admins'
    id = db.Column(db.String(36), primary_key=True, default=gen_uuid)
    username = db.Column(db.String(64), unique=True, nullable=False)
    password_hash = db.Column(db.String(256), nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    def set_password(self, password):
        self.password_hash = generate_password_hash(password)

    def check_password(self, password):
        return check_password_hash(self.password_hash, password)
