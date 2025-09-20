import json
import logging
from concurrent.futures import ProcessPoolExecutor, as_completed

import fitz
import numpy as np
from PIL import Image
from pathlib import Path
import cv2

import sys
FORMAT = '%(asctime)-s %(name)s %(funcName)s %(lineno)d %(levelname)-8s %(message)s'
logging.basicConfig(format=FORMAT, stream=sys.stderr, level=logging.INFO)

LOGGER = logging.getLogger(__name__)

def fitz_doc_to_image(doc, dpi=200) -> dict:
    """Convert fitz.Document to image, Then convert the image to numpy array.

    Args:
        doc (_type_): pymudoc page
        dpi (int, optional): reset the dpi of dpi. Defaults to 200.

    Returns:
        dict:  {'img': numpy array, 'width': width, 'height': height }
    """

    mat = fitz.Matrix(dpi / 72, dpi / 72)
    pm = doc.get_pixmap(matrix=mat, alpha=False)

    # If the width or height exceeds 4500 after scaling, do not scale further.
    if pm.width > 4500 or pm.height > 4500:
        pm = doc.get_pixmap(matrix=fitz.Matrix(1, 1), alpha=False)

    img = Image.frombytes('RGB', (pm.width, pm.height), pm.samples)
    img = np.array(img)

    img_dict = {'img': img, 'width': pm.width, 'height': pm.height}

    return img_dict

def doc_2_img(pdf_path, dpi, pics_dir, index):
    # 此处之所以重新读取pdf，是因为doc无法序列化，故而无法在多进程中传递。
    docs = fitz.open(pdf_path)
    doc = docs[index]
    img = fitz_doc_to_image(doc, dpi=dpi)['img']
    ret, buf = cv2.imencode('.png', img)  # 也可以改为.png等格式
    if not ret:
        raise ValueError("图像编码失败")

    img_path = str(pics_dir / f'{index:04d}.png')
    # 使用numpy的tofile方法写入文件
    buf.tofile(img_path)
    LOGGER.info('written %s', img_path)


def pdf_2_pics(pdf_path,
               start_page=None,  # 从1开始
               end_page=None,  # 含end，即前闭后闭
               dpi=200,
               max_workers=4,
               override=False,
               exist_ok=True
               ):
    LOGGER.info('pdf_2_pics enter, pdf_path: %s, start_page: %s, end_page: %s, dpi: %d, max_workers: %d',
                pdf_path, start_page, end_page, dpi, max_workers)
    docs = fitz.open(pdf_path)

    pdf_path = Path(pdf_path)
    pics_dir = pdf_path.parent / pdf_path.stem

    if pics_dir.exists():
        if not exist_ok:
            raise ValueError(f"pics_dir exists: {pics_dir}")

        if not override:
            return str(pics_dir)
    else:
        pics_dir.mkdir(parents=True)

    with ProcessPoolExecutor(max_workers=max_workers) as executor:
        futures = []
        for index, doc in enumerate(docs):
            page_index = index + 1

            if start_page and page_index < start_page:
                continue

            if end_page and page_index > end_page:
                break

            futures.append(executor.submit(doc_2_img, pdf_path, dpi, pics_dir, index))
        for future in as_completed(futures):
            future.result()

    LOGGER.info('pdf_2_pics return, pics_dir: %s', pics_dir)
    return str(pics_dir)


def save_bookmarks(pdf_path, dest_pdf_path, bookmarks=None, title_json_path=None):
    LOGGER.info('save_bookmarks enter, pdf_path: %s, dest_pdf_path: %s, bookmarks: %s, title_json_path: %s',
                pdf_path, dest_pdf_path, bookmarks, title_json_path)
    doc = fitz.open(pdf_path)

    if bookmarks:
        bks = [bk.model_dump() for bk in bookmarks]
    elif title_json_path:
        with open(title_json_path, 'rt', encoding='utf-8', newline='') as f:
            bks = json.load(f)
    else:
        raise ValueError('bookmarks and title_json_path are both empty')

    fitz_bookmarks = []

    for bk in bks:
        grade = bk["grade"]
        title_name = bk["title_name"]
        page_nubmer = bk["page_number"]
        dest_dict = {
            "kind": fitz.LINK_GOTO,
            "page": page_nubmer,
            "to": fitz.Point(0, 0),
        }
        fitz_bookmarks.append([grade, title_name, page_nubmer, dest_dict])

    split_doc = fitz.open()
    split_doc.insert_pdf(doc)
    split_doc.set_toc(fitz_bookmarks)
    split_doc.save(dest_pdf_path)

    doc.close()
    LOGGER.info('save_bookmarks return')


if __name__ == '__main__':
    # save_bookmarks(r'D:\学习\python\Python asyncio 并发编程 (马修·福勒).pdf',
    #                      r'D:\学习\python\Python asyncio 并发编程 (马修·福勒)_bk.pdf',
    #                      r'D:\学习\python\Python asyncio 并发编程 (马修·福勒).json')

    # pdf_2_pics(r'D:\学习\python\Python asyncio 并发编程 (马修·福勒).pdf', max_workers=8)

    save_bookmarks(r'D:\学习\营养学\中国居民膳食指南（2022）.pdf',
                   r'D:\学习\营养学\中国居民膳食指南（2022）_test书签.pdf',
                   title_json_path=r'D:\学习\营养学\中国居民膳食指南（2022）.json')