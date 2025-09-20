import logging
import logging.config
import os, sys
import argparse

from llm_bookmark.bookmark import LLMBookmark


FORMAT = '%(asctime)-s %(name)s %(funcName)s %(lineno)d %(levelname)-8s %(message)s'
logging.basicConfig(format=FORMAT, stream=sys.stderr, level=logging.INFO)


LOGGING_NAME = "llm_bookmark"

def set_logging(verbose=True):
    os.makedirs('log', exist_ok=True)

    # sets up logging for the given name
    level = logging.DEBUG if verbose else logging.INFO

    logging.config.dictConfig({
        "version": 1,
        "disable_existing_loggers": False,
        "formatters": {
            f"{LOGGING_NAME}_fmt": {
                "format": "%(asctime)s %(name)s %(funcName)s %(lineno)d %(levelname)-8s %(message)s"}},
        "handlers": {
            f"{LOGGING_NAME}_rotate_file": {
                "class": "logging.handlers.RotatingFileHandler",
                "formatter": f"{LOGGING_NAME}_fmt",
                "level": level,
                "encoding": "utf-8",
                "filename": "log/bookmark.log",
                "maxBytes": 10 * 1024 * 1024,
                "backupCount": 10},
            f"{LOGGING_NAME}_console": {
                "class": "logging.StreamHandler",
                "formatter": f"{LOGGING_NAME}_fmt",
                "level": level}},
        "loggers": {
            LOGGING_NAME: {
                "level": level,
                "handlers": [f"{LOGGING_NAME}_rotate_file", f"{LOGGING_NAME}_console"],
                "propagate": False,}}})  # 这里如果不指定为False，则默认为True，控制台中会同时写两条，有一条是basicConfig中的，即root的

set_logging()  # run before defining LOGGER
LOGGER = logging.getLogger(LOGGING_NAME)


def parse_args():
    parser = argparse.ArgumentParser()
    parser.add_argument("pdf_path", help="pdf原文件路径")
    parser.add_argument("dest_pdf_path", help="pdf结果文件路径")
    parser.add_argument("--skip-page-ranges", action="extend", nargs="+", type=int,
                        help="需要跳过的页号范围，从0开始算。必须是成对的，比如:0 2 表示跳过0-2页，0 2 7 8 表示跳过0-2，7-8，每一对都是前闭后闭的")
    parser.add_argument("--extra-prompt-path", type=str, default=None,
                        help="额外提示词文本路径，请输入全路径，比如d:/xxx/xxx.txt，注意：该文件的编码字符集必须用utf-8")
    args = parser.parse_args()
    return args


def parse_skip_page_ranges(args):
    if args.skip_page_ranges:
        skip_page_ranges = args.skip_page_ranges
        if len(skip_page_ranges) // 2 * 2 != len(skip_page_ranges):
            raise ValueError('需要跳过的页号范围必须是成对的')

        return [(skip_page_ranges[index], skip_page_ranges[index + 1]) for index in range(0, len(skip_page_ranges), 2)]
    return None


if __name__ == '__main__':
    args = parse_args()
    llm_bookmarkor = LLMBookmark(extra_prompt_path=args.extra_prompt_path)
    llm_bookmarkor.do_bookmark(args.pdf_path, args.dest_pdf_path, skip_page_ranges=parse_skip_page_ranges(args))
