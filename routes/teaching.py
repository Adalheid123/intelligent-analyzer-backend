"""
教学端接口
从原 analysis/app.py 迁移过来
"""
import re
import json
import io
import os
from flask import Blueprint, request, jsonify
import openai
import openpyxl
import docx

teaching_bp = Blueprint('teaching', __name__)


def _get_client(api_key):
    return openai.OpenAI(
        api_key=api_key,
        base_url="https://api.deepseek.com/v1"
    )


@teaching_bp.route('/analyze', methods=['POST'])
def analyze():
    """通用分析 / 自由问答"""
    try:
        data = request.json
        text = data.get('text', '')
        api_key = data.get('api_key', '') or os.environ.get('DEEPSEEK_API_KEY', '')
        is_chat = data.get('is_chat', False)
        messages = data.get('messages', [])

        if not api_key:
            return jsonify({"success": False, "error": "请提供 DeepSeek API Key"}), 400

        client = _get_client(api_key)

        # 自由问答
        if is_chat and messages:
            response = client.chat.completions.create(
                model="deepseek-chat",
                messages=messages,
                temperature=0.7
            )
            result_text = response.choices[0].message.content
            return jsonify({"success": True, "result": result_text})

        # 标准化七字段分析
        if not text:
            return jsonify({"success": False, "error": "请提供文本内容"}), 400

        prompt = f"""请对以下文本进行深度分析，输出JSON格式结果，包含以下7个字段：

1. 情感分析：情感倾向（正向/中性/负向）、情感强度（1-5级）、关键情感词列表
2. 用户意图：意图类型、意图描述
3. 需求紧迫程度：等级（紧急/较急/一般）、评分（1-10）
4. 问题分类：类别、子类
5. 推荐处理路径：动作、理由
6. 置信度：评分（0-1）、说明
7. 判断依据：关键信号列表、分析说明

文本内容：{text}

请只返回JSON，不要有其他内容。"""

        response = client.chat.completions.create(
            model="deepseek-chat",
            messages=[{"role": "user", "content": prompt}],
            temperature=0.3
        )

        result_text = response.choices[0].message.content
        json_match = re.search(r'\{.*\}', result_text, re.DOTALL)
        if json_match:
            result = json.loads(json_match.group())
            return jsonify({"success": True, "result": result})
        else:
            return jsonify({"success": False, "error": "JSON解析失败"}), 500

    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 500


@teaching_bp.route('/analyze/teaching', methods=['POST'])
def analyze_teaching():
    """英语作文四维批改"""
    try:
        data = request.json
        text = data.get('text', '')
        api_key = data.get('api_key', '') or os.environ.get('DEEPSEEK_API_KEY', '')

        if not text:
            return jsonify({"success": False, "error": "请提供作文内容"}), 400
        if not api_key:
            return jsonify({"success": False, "error": "请提供 DeepSeek API Key"}), 400

        client = _get_client(api_key)

        prompt = f"""请对以下英语作文进行批改，输出JSON格式，包含：

1. 语法准确性：评分（0-10）、反馈
2. 词汇丰富度：评分（0-10）、反馈
3. 逻辑连贯性：评分（0-10）、反馈
4. 语用得体性：评分（0-10）、反馈
5. 整体评语
6. 修改优先级：列出3条最重要的修改建议

作文内容：{text}

请只返回JSON。"""

        response = client.chat.completions.create(
            model="deepseek-chat",
            messages=[{"role": "user", "content": prompt}],
            temperature=0.3
        )

        result_text = response.choices[0].message.content
        json_match = re.search(r'\{.*\}', result_text, re.DOTALL)
        if json_match:
            result = json.loads(json_match.group())
            return jsonify({"success": True, "result": result})
        else:
            return jsonify({"success": False, "error": "JSON解析失败"}), 500

    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 500


@teaching_bp.route('/import_students', methods=['POST'])
def import_students():
    """解析上传的学生名单（Excel / Word）"""
    try:
        if 'file' not in request.files:
            return jsonify({"success": False, "error": "没有上传文件"}), 400
        file = request.files['file']
        if file.filename == '':
            return jsonify({"success": False, "error": "文件名为空"}), 400

        school = request.form.get('school', '')
        major = request.form.get('major', '')
        className = request.form.get('class', '')
        if not school or not major or not className:
            return jsonify({"success": False, "error": "缺少学校、专业或班级参数"}), 400

        students = []
        filename = file.filename.lower()

        if filename.endswith('.xlsx') or filename.endswith('.xls'):
            wb = openpyxl.load_workbook(io.BytesIO(file.read()))
            sheet = wb.active
            for row in sheet.iter_rows(min_row=2, values_only=True):
                if row and len(row) >= 2:
                    name = str(row[0]).strip() if row[0] else ''
                    student_id = str(row[1]).strip() if row[1] else ''
                    if name and name != 'None':
                        students.append({"name": name, "student_id": student_id})

        elif filename.endswith('.docx'):
            doc = docx.Document(io.BytesIO(file.read()))
            text = "\n".join([p.text for p in doc.paragraphs if p.text.strip()])
            lines = text.strip().split('\n')
            for line in lines:
                line = line.strip()
                if not line:
                    continue
                parts = re.split(r'[\t,，\s]+', line)
                if len(parts) >= 2:
                    name = parts[0].strip()
                    student_id = parts[1].strip()
                    if name and student_id:
                        students.append({"name": name, "student_id": student_id})
                elif len(parts) == 1:
                    if parts[0].strip():
                        students.append({"name": parts[0].strip(), "student_id": ""})
        else:
            return jsonify({"success": False, "error": "不支持的文件格式，请上传 .xlsx .xls .docx"}), 400

        if not students:
            return jsonify({"success": False, "error": "未能解析到学生数据，请检查文件格式"}), 400

        return jsonify({
            "success": True,
            "message": f"成功解析 {len(students)} 名学生",
            "total": len(students),
            "students": students
        })

    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 500
