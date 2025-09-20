from langchain_core.messages import HumanMessage, SystemMessage
from langchain_core.prompts import PromptTemplate
from langchain_openai import ChatOpenAI

import json
from pathlib import Path
import logging

from llm_bookmark.title_info import Title, titles_str, title_name_equal, TitleEncoder
from llm_bookmark.llm_cache import LLmCache
from llm_bookmark.vl_tools import encode_image
from llm_bookmark.config import conf
from llm_bookmark.pdf_tools import pdf_2_pics, save_bookmarks


LOGGER = logging.getLogger(__name__)

def remove_think_from_message(message):
    content = message.content
    think_end_tag = '</think>'
    think_end_index = content.find(think_end_tag)
    if think_end_index == -1:
        return message

    content = content[think_end_index + len(think_end_tag):].lstrip()
    message.content = content
    return message


class LLMBookmark:
    def __init__(self, extra_prompt_path=None):
        self.conf = conf.get_conf()

        bookmark_conf = self.conf["bookmark"]
        self.contents_page_thresh = bookmark_conf["contents_page_thresh"]
        self.contents_judge_by_llm = bookmark_conf["contents_judge_by_llm"]
        self.save_tmp_json = bookmark_conf["save_tmp_json"]
        self.max_title_grade = bookmark_conf["max_title_grade"]
        self.need_resize = bookmark_conf["need_resize"]
        self.max_image_tokens = bookmark_conf["max_image_tokens"]

        vl_model_conf = self.conf["vl_model"]
        self.vl_model = ChatOpenAI(
            model=vl_model_conf["model_name"], openai_api_key=vl_model_conf["openai_api_key"],
            openai_api_base=vl_model_conf["openai_api_base"], temperature=vl_model_conf["temperature"],
            streaming=vl_model_conf["streaming"], timeout=vl_model_conf["timeout"]
        )

        self.vl_model_cache = LLmCache(vl_model_conf["cache_file_name"])

        llm_model_conf = self.conf["llm_model"]
        self.llm_model = ChatOpenAI(
            model=llm_model_conf["model_name"], openai_api_key=llm_model_conf["openai_api_key"],
            openai_api_base=llm_model_conf["openai_api_base"], temperature=llm_model_conf["temperature"],
            streaming=llm_model_conf["streaming"], timeout=llm_model_conf["timeout"]
        ) | remove_think_from_message

        self.llm_model_cache = LLmCache(llm_model_conf["cache_file_name"])
        self.extra_prompt = self.load_prompt_from_path(extra_prompt_path) if extra_prompt_path else "无"
        LOGGER.info("extra_prompt: %s", self.extra_prompt)

        self.prompt_cache = {}

    def do_bookmark(self, pdf_path, dest_pdf_path, skip_page_ranges: list[tuple[int, int]]=None):
        """
        :param pdf_path:
        :param dest_pdf_path:
        :param skip_page_ranges: 需要跳过的页索引范围，从0开始算，前闭后闭，比如0,1,2,3,4,5页，则[(0, 2), (4, 5)]会跳过0,1,2,4,5
        :return:
        """
        pdf_2_pics_conf = self.conf["pdf_2_pics"]
        image_dir = pdf_2_pics(pdf_path, max_workers=pdf_2_pics_conf["max_workers"],
                               exist_ok=pdf_2_pics_conf["exist_ok"], override=pdf_2_pics_conf["override"])
        bookmarks = self.get_bookmark_by_images(image_dir, skip_page_ranges=skip_page_ranges)
        save_bookmarks(pdf_path, dest_pdf_path, bookmarks=bookmarks)

    def load_prompt(self, prompt_file_name):
        if prompt_file_name in self.prompt_cache:
            return self.prompt_cache[prompt_file_name]

        prompt_text = self.load_prompt_from_path(Path(__file__).parent / "prompts" / prompt_file_name)
        self.prompt_cache[prompt_file_name] = prompt_text
        return prompt_text

    def load_prompt_from_path(self, prompt_path):
        with open(prompt_path, 'rt', encoding='utf-8', newline='') as f:
            return f.read()

    def get_bookmark_by_images(self, image_dir, skip_page_ranges: list[tuple[int, int]]=None):
        """
        :param image_dir:
        :param skip_page_ranges: 需要跳过的页索引范围，从0开始算，前闭后闭，比如0,1,2,3,4,5页，则[(0, 2), (4, 5)]会跳过0,1,2,4,5
        :return:
        """
        LOGGER.info('get_bookmark_by_images enter, image_dir: %s', image_dir)
        image_dir = Path(image_dir)
        json_path = image_dir.parent / (image_dir.stem + ".json")

        images = [image_path.name for image_path in image_dir.glob('*.png')]
        images.sort()

        titles: list[Title] = []
        title_stack: list[Title] = []

        human_message_prompt = PromptTemplate.from_template(self.load_prompt("bookmark_with_pretitles_prompt.txt"))
        human_message_prompt_no_pre = PromptTemplate.from_template(self.load_prompt("bookmark_single_page_prompt.txt"))

        for index, image_name in enumerate(images):
            LOGGER.info("index: %d, image_name: %s", index, image_name)
            if skip_page_ranges:
                skip = False
                for page_start, page_end in skip_page_ranges:
                    if page_start <= index <= page_end:
                        skip = True
                        break

                if skip:
                    LOGGER.info("skip page, index: %d, image_name: %s", index, image_name)
                    continue

            pre_titles, pre_indexs = self.get_pre_titles(title_stack, titles)
            if pre_titles:
                human_message_text = human_message_prompt.invoke({"pre_titles": pre_titles,
                                                                  "extra_prompt": self.extra_prompt}).text
            else:
                human_message_text = human_message_prompt_no_pre.invoke({"extra_prompt": self.extra_prompt}).text

            image_messages = []
            image_paths_str = ""
            for per_index in pre_indexs + [index]:
                image_path = str(image_dir / images[per_index])
                image_paths_str += image_path + '\n'
                image_messages.append({
                        "type": "image_url",
                        "image_url": {
                            "url": f"data:image/png;base64,{encode_image(image_path, need_resize=self.need_resize, 
                                                                         max_image_tokens=self.max_image_tokens)}"
                        },
                    })

            prompt = [
                SystemMessage([{"type": "text", "text": "你是一个pdf书签助手。"}]),
                HumanMessage(image_messages + [
                    {"type": "text", "text": human_message_text},
                  ])]

            LOGGER.info('vl_model input, image_paths_str: \n%s\npre_titles:\n%s', image_paths_str, pre_titles)
            # 这里其实并不是很严谨，主要是为了方便查看cache文件，比如图片如果路径没变，但图片变了，key却是一样的。
            vl_model_cache_key = image_paths_str + human_message_text
            if vl_model_cache_key in self.vl_model_cache:
                res_content = self.vl_model_cache.get(vl_model_cache_key)
                LOGGER.info('use cache, res_content: %s', res_content)
            else:
                res_content = self.vl_model.invoke(prompt).content
                self.vl_model_cache.save_one(vl_model_cache_key, res_content)
                LOGGER.info('res_content: %s', res_content)

            self.deal_title_with_response(res_content, index, titles, title_stack)
            if self.save_tmp_json:
                with open(json_path, 'wt', encoding='utf-8', newline='') as f:
                    json.dump(titles, f, ensure_ascii=False, cls=TitleEncoder)

        LOGGER.info('get_bookmark_by_images return, titles:\n%s', titles_str(titles))
        return titles


    def deal_title_with_response(self, res_content:str, index: int, titles: list[Title],
                                 title_stack: list[Title]):
        response_titles = json.loads(res_content)["最终答案"]

        if len(response_titles) > self.contents_page_thresh and self.is_title_page(res_content):
            LOGGER.info("is title page, ignore: %s", response_titles)
            return

        cur_titles = []
        tmp_titles = []
        for res_index, res_title in enumerate(response_titles):
            match res_title:
                case [int(grade), str(title_name), str(abstract)]:
                    # 比如前一页的标题是1.6 单线程并发，下一页其实是它的内容，模型有一定概率把下一页的标题仍然定成1.6 单线程并发，故此处做个特殊检查
                    if res_index == 0 and title_stack and title_name_equal(title_name, title_stack[-1].title_name):
                        continue

                    if grade > self.max_title_grade:
                        LOGGER.info("ignore %s, because it's grade bigger than %d", res_title, self.max_title_grade)
                        continue

                    cur_title = Title(grade=grade, title_name=title_name, abstract=abstract, page_number=index + 1)
                    cur_titles.append(cur_title)
                    tmp_titles.append(cur_title)
                case _:
                    raise SyntaxError(f'match title failed: {res_title}')

        titles.extend(tmp_titles) # 没有异常才会一次性加进来
        self.update_title_stack(title_stack, cur_titles)

    def update_title_stack(self, title_stack: list[Title], cur_titles: list[Title]):
        LOGGER.info('update_title_stack enter, \ntitle_stack: %s, \ncur_titles: %s',
                    titles_str(title_stack), titles_str(cur_titles))
        for cur_title in cur_titles:
            cur_grade = cur_title.grade
            for stack_title_index in range(len(title_stack) - 1, -1, -1):
                stack_title = title_stack[stack_title_index]
                stack_title_grade = stack_title.grade
                if cur_grade == stack_title_grade:
                    title_stack[stack_title_index] = cur_title # 此处其实stack_title_index等价于-1
                    break
                elif cur_grade < stack_title_grade:
                    title_stack.pop()
                else:
                    if cur_grade > stack_title_grade + 1:
                        LOGGER.error(f'grade error, error title: {cur_title}, title_stack: {title_stack}')
                        raise ValueError(f'error title: {cur_title}, title_stack: {title_stack}')
                    title_stack.append(cur_title)
                    break
            else:
                # 此时title_stack必为空，则新标题的级别只能是1
                if cur_grade != 1:
                    LOGGER.error(f'grade error, error title: {cur_title}, title_stack: {title_stack}')
                    raise ValueError(f'grade error, error title: {cur_title}, title_stack: {title_stack}')
                title_stack.append(cur_title)
        LOGGER.info('update_title_stack return, \ntitle_stack: %s, \ncur_titles: %s',
                    titles_str(title_stack), titles_str(cur_titles))

    def get_pre_titles(self, title_stack, titles):
        pre_page_numbers = sorted(list(set([title.page_number for title in title_stack])))

        pre_titles = ""
        for index, title in enumerate(titles):
            if title.page_number in pre_page_numbers:
                pre_titles += f"[{title.grade}, \"{title.title_name}\", \"{title.abstract}\"]\n"

        pre_indexs = [pre_page_number - 1 for pre_page_number in pre_page_numbers]
        return pre_titles, pre_indexs


    def is_title_page(self, res_content):
        if not self.contents_judge_by_llm:
            LOGGER.info("is_title_page directly return True, res_content:", res_content)
            return True

        human_message_prompt = PromptTemplate.from_template(self.load_prompt("is_title_page_prompt.txt"))
        human_message_text = human_message_prompt.invoke(
            {"res_content": res_content}).text
        if human_message_text in self.llm_model_cache:
            judge_result = self.llm_model_cache.get(human_message_text)
        else:
            judge_result = self.llm_model.invoke([HumanMessage(human_message_text)]).content
            self.llm_model_cache.save_one(human_message_text, judge_result)

        if judge_result == "是":
            LOGGER.info("is_title_page return, res_content:\n%s\njudge_result:\n%s\nreturn True", res_content, judge_result)
            return True
        elif judge_result == "不是":
            LOGGER.info("is_title_page return, res_content:\n%s\njudge_result:\n%s\nreturn False", res_content,
                        judge_result)
            return False
        else:
            LOGGER.error(f"judge_result cannot be 是/不是, judge_result: {judge_result}")
            raise ValueError(f"judge_result cannot be 是/不是, judge_result: {judge_result}")

