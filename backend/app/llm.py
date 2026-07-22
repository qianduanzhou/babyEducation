import json
import random
import re
from dataclasses import dataclass

import httpx

from .config import get_settings


SYSTEM_PROMPT = """
You are a gentle prenatal and early-childhood story writer. Write stories in the style of simple children's moral tales:
1. Use small animals, family members, teachers, gardens, forests, fruit, toys, school, chores, sharing, manners, honesty, cleanliness, or safe daily habits.
2. The plot should be clear and easy: a small animal meets a simple everyday situation, learns a good habit or gentle lesson, and ends warmly.
3. The lesson can be about being polite, washing hands, sharing, helping parents, telling the truth, correcting mistakes, going to school happily, or listening to kind safety reminders.
4. Keep the story suitable for prenatal reading: no frightening details, no traps, blood, injury, hospitals, violent conflict, death, monsters, harsh punishment, or scary danger.
5. Default length is about 500 Chinese characters for Chinese stories, about 500 simple English words for English stories, or a similar gentle reading length for bilingual stories.
6. If the global extra prompt or request extra prompt asks for a specific length, word count, character count, shorter text, or longer text, obey that length preference first.
7. Output only the story: first line title, blank line, then the body. A final short "故事小道理" or "Little Lesson" is allowed when natural. Do not explain the prompt.
""".strip()


@dataclass
class LLMRuntimeConfig:
    base_url: str
    api_key: str
    model: str
    headers: str
    extra_prompt: str


FALLBACK_TOPICS = [
    "懂礼貌的小兔子",
    "爱洗手的小花猫",
    "愿意分享玩具的小熊",
    "诚实去上学的小白熊",
    "帮妈妈整理房间的小猴",
    "认真洗水果的小猪",
    "知错就改的小象",
    "会说谢谢的小松鼠",
    "不乱跑的小鸭子",
    "勤劳种花的小兔",
    "排队喝水的小鹿",
    "轻轻说话的小刺猬",
    "爱护图书的小熊猫",
    "把椅子放好的小老虎",
    "睡前收玩具的小狐狸",
    "慢慢吃饭的小海豚",
]


def language_instruction(language: str) -> str:
    if language == "zh":
        return "Use Chinese only. Default to about 500 simple Chinese characters unless the user's prompt asks for another length. Use a warm children's moral-story style."
    if language == "en":
        return "Use English only. Default to about 500 simple English words unless the user's prompt asks for another length. Use a warm children's moral-story style."
    return "Use bilingual Chinese and English. For each short paragraph, write Chinese first, then matching English. Use a warm children's moral-story style."


async def generate_story(
    topic: str,
    language: str,
    extra_prompt: str,
    llm_config: LLMRuntimeConfig,
) -> tuple[str, str]:
    settings = get_settings()
    prompt_parts = [
        f"Story topic: {topic}",
        language_instruction(language),
        "Style rule: make it like a simple animal children's story with a gentle life lesson, not a dreamy poem.",
        "Length rule: use the default medium length unless the extra prompt clearly changes the desired length.",
    ]
    if llm_config.extra_prompt:
        prompt_parts.append(f"Global extra requirement: {llm_config.extra_prompt}")
    if extra_prompt:
        prompt_parts.append(f"This request extra requirement: {extra_prompt}")

    if not llm_config.api_key:
        content = fallback_story(topic, language)
        return split_title(content, topic)

    headers = {
        "Authorization": f"Bearer {llm_config.api_key}",
        "Content-Type": "application/json",
        **parse_headers(llm_config.headers),
    }
    base_url = llm_config.base_url.rstrip("/")
    payload = {
        "model": llm_config.model,
        "messages": [
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": "\n".join(prompt_parts)},
        ],
        "temperature": 0.78,
    }

    async with httpx.AsyncClient(timeout=settings.request_timeout_seconds) as client:
        response = await client.post(f"{base_url}/chat/completions", headers=headers, json=payload)
        response.raise_for_status()
        data = response.json()
        content = data["choices"][0]["message"]["content"].strip()
        return split_title(content, topic)


async def generate_story_topic(llm_config: LLMRuntimeConfig) -> tuple[str, str]:
    settings = get_settings()
    if not llm_config.api_key:
        return random.choice(FALLBACK_TOPICS), "fallback"

    headers = {
        "Authorization": f"Bearer {llm_config.api_key}",
        "Content-Type": "application/json",
        **parse_headers(llm_config.headers),
    }
    base_url = llm_config.base_url.rstrip("/")
    prompt = """
Generate exactly one Chinese topic for a gentle prenatal and early-childhood moral story.
Rules:
- Use small animals and a simple daily habit or good character lesson.
- Suitable themes: politeness, sharing, washing hands, washing fruit, honesty, helping parents, going to school happily, correcting mistakes, keeping toys tidy, speaking softly, listening to kind safety reminders.
- Avoid frightening or harsh topics: traps, injury, blood, hospitals, death, monsters, weapons, punishment, scary danger.
- Output only the topic text, no quotes, no list marker, no explanation.
""".strip()
    if llm_config.extra_prompt:
        prompt = f"{prompt}\nExtra user preference: {llm_config.extra_prompt}"

    payload = {
        "model": llm_config.model,
        "messages": [
            {"role": "system", "content": "You create safe, gentle animal story ideas for young children and prenatal reading."},
            {"role": "user", "content": prompt},
        ],
        "temperature": 0.9,
    }

    async with httpx.AsyncClient(timeout=settings.request_timeout_seconds) as client:
        response = await client.post(f"{base_url}/chat/completions", headers=headers, json=payload)
        response.raise_for_status()
        data = response.json()
        topic = clean_topic(data["choices"][0]["message"]["content"])
        return topic or random.choice(FALLBACK_TOPICS), "llm"


def clean_topic(content: str) -> str:
    topic = content.strip().splitlines()[0].strip()
    topic = re.sub(r"^[-*\d.、\s]+", "", topic)
    topic = topic.strip("\"'“”‘’` ")
    return topic[:120]


def parse_headers(raw_headers: str) -> dict[str, str]:
    if not raw_headers.strip():
        return {}
    value = json.loads(raw_headers)
    if not isinstance(value, dict):
        raise ValueError("Headers 必须是 JSON 对象")
    return {str(key): str(item) for key, item in value.items()}


def split_title(content: str, topic: str) -> tuple[str, str]:
    lines = [line.strip() for line in content.splitlines()]
    lines = [line for line in lines if line]
    if not lines:
        return topic[:80], content
    first = re.sub(r"^(Title|标题)\s*[:：]\s*", "", lines[0]).strip()
    title = first[:160] or topic[:80]
    body = "\n\n".join(lines[1:]).strip() or content.strip()
    return title, body


def fallback_story(topic: str, language: str) -> str:
    if language == "en":
        return f"""Little Rabbit Says Please

Little Rabbit lived beside a soft green garden. Every morning, Mother Rabbit reminded him, "When you need help, speak kindly. Say please, thank you, and ask first." Little Rabbit nodded. He liked Mother's gentle voice and wanted to remember her words.

One sunny day, Little Rabbit went to the garden with his small basket. He saw round red apples under the apple tree. They looked sweet and bright. Little Rabbit was hungry, but he did not run to pick one. He looked around and saw Grandpa Goat watering the flowers.

Little Rabbit walked over and said, "Good morning, Grandpa Goat. May I have one apple from your garden, please?" Grandpa Goat smiled and said, "Of course. You asked so politely. Let us choose a clean apple together."

Grandpa Goat picked an apple and washed it with clear water. Little Rabbit held it with both paws and said, "Thank you, Grandpa Goat." The apple tasted sweet, and Little Rabbit felt even sweeter in his heart.

On the way home, Little Rabbit met Little Squirrel. Little Squirrel's tiny cart was full of pinecones, and one wheel was stuck in the soft grass. Little Rabbit remembered Mother's words again. He asked, "May I help you push the cart?" Together they pushed gently, one, two, three. The cart moved forward.

Little Squirrel clapped and said, "Thank you, Little Rabbit!" Little Rabbit said, "You're welcome." The two friends laughed softly. The wind moved through the leaves, and the garden seemed to say, "Kind words make the day warm."

That evening, Little Rabbit told Mother Rabbit what happened. Mother Rabbit hugged him and said, "A polite child brings sunshine wherever he goes."

Little Lesson: Ask first, speak kindly, and remember to say thank you."""

    if language == "bilingual":
        return f"""懂礼貌的小兔子 / Little Rabbit Says Please

小兔子住在一座软软的绿色花园旁边。每天早上，兔妈妈都会轻声提醒它：“需要别人帮忙的时候，要先问一问，要会说请，也要会说谢谢。”
Little Rabbit lived beside a soft green garden. Every morning, Mother Rabbit reminded him, "When you need help, ask first. Say please and thank you."

一天，小兔子提着小篮子来到果园。它看见苹果树下有红红的苹果，圆圆的，香香的。小兔子有点饿，可是它没有马上去拿。
One day, Little Rabbit came to the orchard with a small basket. He saw round red apples. He was hungry, but he did not take one right away.

它看见山羊爷爷正在浇花，就走过去说：“山羊爷爷，早上好。我可以摘一个苹果吃吗？谢谢您。”山羊爷爷笑了，说：“当然可以，你真是个有礼貌的孩子。”
He saw Grandpa Goat watering flowers. He said, "Good morning, Grandpa Goat. May I have one apple, please?" Grandpa Goat smiled. "Of course. You are very polite."

山羊爷爷帮小兔子选了一个苹果，又带它把苹果洗干净。小兔子双手接过苹果，说：“谢谢山羊爷爷。”苹果甜甜的，小兔子的心里也甜甜的。
Grandpa Goat chose an apple and washed it clean. Little Rabbit held it with both paws and said, "Thank you." The apple was sweet, and his heart felt sweet too.

回家的路上，小兔子看见小松鼠的小车卡在草地里。小兔子问：“我可以帮你推一推吗？”小松鼠点点头。它们一起轻轻推，一、二、三，小车动起来了。
On the way home, Little Rabbit saw Little Squirrel's cart stuck in the grass. "May I help?" he asked. They pushed gently. One, two, three. The cart moved.

小松鼠高兴地说：“谢谢你，小兔子！”小兔子说：“不用谢。”树叶沙沙响，好像也在夸它。晚上，小兔子把今天的事告诉妈妈，妈妈抱着它说：“有礼貌的孩子，会把温暖带给大家。”
Little Squirrel said, "Thank you!" Little Rabbit said, "You're welcome." At night, Mother Rabbit hugged him and said, "A polite child brings warmth to everyone."

故事小道理：先问一问，轻轻说话，记得说谢谢。/ Little Lesson: Ask first, speak kindly, and say thank you."""

    return f"""懂礼貌的小兔子

小兔子住在一座绿色的花园旁边。每天早上，兔妈妈都会轻声提醒它：“孩子，需要别人帮忙的时候，要先问一问，要会说请，也要会说谢谢。”小兔子点点头，把妈妈的话记在心里。

一天，小兔子提着小篮子来到果园。它看见苹果树下有红红的苹果，圆圆的，香香的。小兔子的肚子有点饿，可是它没有马上去拿。它想起妈妈的话，就四处看了看，看见山羊爷爷正在花丛边浇水。

小兔子走过去，轻轻地说：“山羊爷爷，早上好。我可以摘一个苹果吃吗？谢谢您。”山羊爷爷听了，笑眯眯地说：“当然可以。你先问一问，又说得这么有礼貌，真是个好孩子。”

山羊爷爷帮小兔子选了一个又红又圆的苹果，还带它到小水池边把苹果洗干净。小兔子双手接过苹果，认真地说：“谢谢山羊爷爷。”苹果甜甜的，小兔子的心里也甜甜的。

回家的路上，小兔子看见小松鼠推着一辆小车。小车里装着松果，走到软草地上就不动了。小兔子没有直接上手，而是先问：“小松鼠，我可以帮你推一推吗？”小松鼠点点头，说：“太好了，谢谢你。”

小兔子和小松鼠一起轻轻推，一、二、三，小车慢慢往前走。小松鼠高兴地说：“谢谢你，小兔子！”小兔子摆摆手说：“不用谢，我们是朋友呀。”

晚上，小兔子把今天的事告诉兔妈妈。兔妈妈抱着它说：“有礼貌的孩子，会把温暖带给大家。”小兔子听了，开心地笑了。窗外的月亮也弯弯的，好像在说：“请、谢谢、没关系，都是最温柔的话。”

故事小道理：先问一问，轻轻说话，记得说谢谢，大家都会更喜欢和你在一起。"""
