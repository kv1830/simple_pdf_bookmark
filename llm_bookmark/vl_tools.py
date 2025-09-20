import base64
import json
import math
from pathlib import Path

import cv2
import numpy as np


def imread(path, flags=cv2.IMREAD_COLOR):
    return cv2.imdecode(np.fromfile(path, np.uint8), flags)


def imwrite(path, im):
    try:
        cv2.imencode(Path(path).suffix, im)[1].tofile(path)
        return True
    except Exception:
        return False

cv2.imread, cv2.imwrite = imread, imwrite


def resize_by_tokens(image_path, min_pixels = 28 * 28 * 4, max_pixels = 1280 * 28 * 28):
    """
    :param image_path:
    :param min_pixels: 图像的Token下限：4个Token
    :param max_pixels: 图像的Token上限：1280个Token
    :return:
    """
    image_path = Path(image_path)
    image_path_reize_dir = Path(str(image_path.parent) + '_rezied')
    image_path_reize_dir.mkdir(exist_ok=True)
    resized_img_path = image_path_reize_dir / image_path.name
    if resized_img_path.exists():
        return str(resized_img_path)

    # 打开指定的PNG图片文件
    image = cv2.imread(str(image_path))

    # 获取图片的原始尺寸
    height, width = image.shape[:2]

    # 将高度调整为28的整数倍
    h_bar = round(height / 28) * 28
    # 将宽度调整为28的整数倍
    w_bar = round(width / 28) * 28

    # 对图像进行缩放处理，调整像素的总数在范围[min_pixels,max_pixels]内
    if h_bar * w_bar > max_pixels:
        # 计算缩放因子beta，使得缩放后的图像总像素数不超过max_pixels
        beta = math.sqrt((height * width) / max_pixels)
        # 重新计算调整后的高度，确保为28的整数倍
        h_bar = math.floor(height / beta / 28) * 28
        # 重新计算调整后的宽度，确保为28的整数倍
        w_bar = math.floor(width / beta / 28) * 28
    elif h_bar * w_bar < min_pixels:
        # 计算缩放因子beta，使得缩放后的图像总像素数不低于min_pixels
        beta = math.sqrt(min_pixels / (height * width))
        # 重新计算调整后的高度，确保为28的整数倍
        h_bar = math.ceil(height * beta / 28) * 28
        # 重新计算调整后的宽度，确保为28的整数倍
        w_bar = math.ceil(width * beta / 28) * 28
    else:
        return image_path

    print(f'resize {image_path} to {w_bar, h_bar}')
    resized_img = cv2.resize(image, (w_bar, h_bar), interpolation=cv2.INTER_LINEAR)
    cv2.imwrite(str(resized_img_path), resized_img)
    return str(resized_img_path)


#  base 64 编码格式
def encode_image(image_path, need_resize=True, max_image_tokens=1280):
    if need_resize:
        image_path = resize_by_tokens(image_path, max_pixels=max_image_tokens * 28 * 28)

    with open(image_path, "rb") as image_file:
        return base64.b64encode(image_file.read()).decode("utf-8")
