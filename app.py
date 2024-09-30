from flask import Flask, render_template, request, send_file, redirect, url_for
import os
import cv2
import numpy as np
from PIL import Image, ImageChops

app = Flask(__name__, static_url_path='/static', static_folder='static')

UPLOAD_FOLDER = os.path.join(app.static_folder, 'upload')
FORGED_FOLDER = os.path.join(app.static_folder, 'forged')

for folder in [UPLOAD_FOLDER, FORGED_FOLDER]:
    if not os.path.exists(folder):
        os.makedirs(folder)

app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER
app.config['FORGED_FOLDER'] = FORGED_FOLDER


def detect_image_forgery(image_path):
    """
    使用误差级分析(ELA)检测图像是否被篡改或伪造，并使用红色标记差异区域。
    Args:
        image_path: 图像文件的路径。
    Returns:
        一个元组，包含：
          - 是否存在伪造的可能性（True/False）。
          - 可疑的伪造区域的误差图像路径（如果有的话）。
    """
    original = Image.open(image_path)

    # 检查图像是否为 RGBA 模式，如果是，转换为 RGB 模式
    if original.mode == 'RGBA':
        original = original.convert('RGB')

    # 将图像保存为较低质量的 JPEG 格式
    ela_path = image_path.replace('.jpg', '_ela.jpg')
    original.save(ela_path, 'JPEG', quality=90)
    
    # 重新打开压缩后的图像
    compressed = Image.open(ela_path)
    
    # 计算原始图像和压缩图像之间的差异
    ela_image = ImageChops.difference(original, compressed)
    
    # 增强差异并将显著差异区域标记为红色
    ela_image = ela_image.convert('RGB')  # 确保图像是RGB模式
    width, height = ela_image.size
    pixels = ela_image.load()

    # 遍历像素并将差异较大的部分标记为红色
    threshold = 50  # 差异阈值，越小越敏感
    for x in range(width):
        for y in range(height):
            r, g, b = pixels[x, y]
            # 如果差异足够大，将其标记为红色
            if r > threshold or g > threshold or b > threshold:
                pixels[x, y] = (255, 0, 0)  # 将差异区域标记为红色

    # 将 ELA 图像保存到 FORGED_FOLDER
    output_filename = os.path.basename(image_path).replace('.jpg', '_ela_output.jpg')
    ela_image_path = os.path.join(app.config['FORGED_FOLDER'], output_filename)
    ela_image.save(ela_image_path)

    # 判断是否存在明显的误差区域
    max_diff = ela_image.getextrema()[1][1]  # 获取最大差异值
    if max_diff > 20:  # 根据实际测试情况可以调整该阈值
        return True, ela_image_path
    else:
        return False, None


@app.route('/', methods=['GET', 'POST'])
def upload_file():
    if request.method == 'POST':
        if 'file' not in request.files:
            return render_template('index.html', message='没有文件部分')
        file = request.files['file']
        if file.filename == '':
            return render_template('index.html', message='未选择文件')
        if file:
            filename = os.path.join(app.config['UPLOAD_FOLDER'], file.filename)
            file.save(filename)

            is_forged, ela_image_path = detect_image_forgery(filename)

            if is_forged:
                output_filename = os.path.basename(ela_image_path)
                output_path = os.path.join(app.config['FORGED_FOLDER'], output_filename)
                return render_template('result.html', 
                                       forged=True, 
                                       original_image=file.filename, 
                                       processed_image=output_filename)
            else:
                return render_template('result.html', 
                                       forged=False, 
                                       message='图像未检测到伪造或篡改的迹象。')
    return render_template('index.html')

@app.route('/download/<filename>')
def download_file(filename):
    return send_file(os.path.join(app.config['FORGED_FOLDER'], filename), as_attachment=True)

if __name__ == '__main__':
    app.run(debug=True, host='127.0.0.1')
