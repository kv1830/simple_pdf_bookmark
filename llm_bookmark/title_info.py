from langchain_openai.chat_models import ChatOpenAI
from langchain_core.messages import HumanMessage, SystemMessage

from pydantic import BaseModel, Field
from langchain_openai import ChatOpenAI

from json import JSONEncoder

class Title(BaseModel):
    """
    标题对象，封装了标题级别，标题，摘要。例如
    {'grade': 1, 'title_name': '第1章 langchain大语言模型基础',
    'abstract': '本章深入解析LangChain构建模块如何映射大语言模型概念，以及它们如何通过有效组合助力应用开发。',
    'page_number': 1}
    """
    grade: int = Field(description="标题级别，从1开始。")
    title_name: str = Field(description="标题。")
    abstract: str = Field(description="该标题下内容的摘要。")
    page_number: int = Field(description="第几页，按我发你的图片序号来定，不是按图中页脚上的标号定，从1开始。")

    def __str__(self):
        return f"[{self.grade}, \"{self.title_name}\", \"{self.abstract}\", {self.page_number}]\n"


class Anwser(BaseModel):
    """包含关键思考以及标题列表。"""

    key_thoughts: str = Field(description="提取标题时一些重要的思考点，有助于正确提取标题，请逐页思考。例如：第1页，图片顶端的'langchain'学习是页眉，不能把它当作标题。")
    titles: list[Title] = Field(description="""
    该页的标题列表，例如: 
    [{'grade': 1, 'title_name': '第1章 langchain大语言模型基础', 'abstract': '本章深入解析LangChain构建模块如何映射大语言模型概念，以及它们如何通过有效组合助力应用开发。', 'page_number': 1},
    {'grade': 2, 'title_name': 'LangChain环境配置', 'abstract': '介绍如何配置好LangChain环境', 'page_number': 1}
    {'grade': 2, 'title_name': '在LangChain中使用LLMs', 'abstract': 'LangChain提供了两个简单的接口来与任何LLM API提供商交互：聊天模型, LLMs', 'page_number': 2}
    ]""")

    def __str__(self):
        return f"key_thoughts: \n{self.key_thoughts}\ntitles: \n{self.titles}"


def titles_str(titles: list[Title]):
    s = "["
    for title in titles:
        s += str(title)
    s += "]"
    return s


def title_name_equal(title_name1:str, title_name2: str):
    return title_name1.lower().strip() == title_name2.lower().strip()


class TitleEncoder(JSONEncoder):
    def default(self, o):
        return o.dict()

