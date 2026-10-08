"""
发音评测接口
转发音频到本地 Echoic（通过 NATAPP 暴露），返回评分
"""
import os
import httpx
from flask import Blueprint, request, jsonify

pronunciation_bp = Blueprint('pronunciation', __name__)

# Echoic 地址：优先读环境变量，方便 NATAPP 地址变化时不用改代码
ECHOIC_BASE_URL = os.environ.get('ECHOIC_BASE_URL', 'http://localhost:8000')

# 请求 Echoic 的超时（模型推理慢，给足时间）
ECHOIC_TIMEOUT = float(os.environ.get('ECHOIC_TIMEOUT', '120'))


@pronunciation_bp.route('/evaluate', methods=['POST'])
def evaluate():
    """
    发音评测
    ---
    接收（multipart/form-data）：
      - file: 音频文件（webm / wav / mp3）
      - question_reference: 参考文本，必填
    返回：
      - Echoic 的评分 JSON
    """
    # 1. 校验音频
    if 'file' not in request.files:
        return jsonify({'success': False, 'error': '缺少音频文件（字段名应为 file）'}), 400

    audio = request.files['file']
    if audio.filename == '':
        return jsonify({'success': False, 'error': '音频文件为空'}), 400

    # 2. 校验参考文本
    reference = request.form.get('question_reference', '').strip()
    if not reference:
        return jsonify({'success': False, 'error': '缺少 question_reference（参考文本）'}), 400

    # 3. 组装转发给 Echoic 的表单
    files = {
        'file': (audio.filename, audio.stream, audio.mimetype or 'audio/webm')
    }
    data = {
        'question_type':       request.form.get('question_type', 'read_aloud'),
        'question_language':   request.form.get('question_language', 'en'),
        'question_prompt':     request.form.get('question_prompt', 'Read the following text aloud:'),
        'question_difficulty': request.form.get('question_difficulty', 'intermediate'),
        'question_reference':  reference,
        'timer_secs':          request.form.get('timer_secs', '30'),
    }

    # 4. 转发到 Echoic
    target = f'{ECHOIC_BASE_URL.rstrip("/")}/api/oral/attempts'
    try:
        with httpx.Client(timeout=ECHOIC_TIMEOUT) as client:
            resp = client.post(target, files=files, data=data)
    except httpx.TimeoutException:
        return jsonify({'success': False, 'error': 'Echoic 评测超时，请重试'}), 504
    except httpx.ConnectError:
        return jsonify({
            'success': False,
            'error': f'无法连接 Echoic（{ECHOIC_BASE_URL}），请确认本地服务和隧道已启动'
        }), 502

    # 5. 返回 Echoic 的结果
    if resp.status_code >= 400:
        return jsonify({
            'success': False,
            'error': f'Echoic 返回错误 {resp.status_code}',
            'detail': resp.text[:500]
        }), 502

    try:
        result = resp.json()
    except ValueError:
        return jsonify({'success': False, 'error': 'Echoic 返回的不是 JSON', 'raw': resp.text[:500]}), 502

    return jsonify({'success': True, 'result': result}), 200
