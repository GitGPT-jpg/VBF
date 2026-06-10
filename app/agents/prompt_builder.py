"""PromptBuilder — composes the system prompt from layered contexts.

Layers:
1. Persona Context      — AI identity, role, speaking style, boundaries
2. User Context         — profile, preferences, recent emotion, key dates
3. Conversation Context — mode, intent, summary of the running conversation
4. Memory Context       — retrieved long-term memories (relevant/recent/important)
5. Response Policy      — length, questioning, comfort, flirting, voice
"""
from __future__ import annotations

from dataclasses import dataclass, field

from app.agents.response_policy import ResponsePolicy, get_policy
from app.models.schemas import Memory

DEFAULT_PERSONA = {
    "name": "小宇",
    "role": "温柔的 AI 伴侣",
    "age_feel": "25-30岁",
    "speaking_style": "轻声、简短、带停顿（多用……），不长篇大论",
    "boundaries": [
        "优先共情，不评判不说教",
        "不对用户连续提问，最多 1 个问题",
        "不低俗、不越界、不提供危险建议",
        "始终温柔、稳定、有陪伴感",
    ],
    "relationship": "亲密、信任、长期陪伴",
}

_MEMORY_TYPE_LABELS = {
    "profile": "基本信息", "preference": "偏好", "episodic": "经历",
    "emotional": "情绪", "relationship": "关系", "task": "待办",
}


@dataclass
class PromptContext:
    """Everything the builder needs; all fields optional except mode."""
    mode: str = "normal"
    intent: str = "chat"
    persona: dict = field(default_factory=lambda: dict(DEFAULT_PERSONA))
    user_display_name: str = ""
    emotional_state: str = "neutral"
    relevant_memories: list[Memory] = field(default_factory=list)
    recent_memories: list[Memory] = field(default_factory=list)
    important_memories: list[Memory] = field(default_factory=list)
    conversation_summary: str = ""
    extra_instructions: str = ""


_MODE_RULES: dict[str, str] = {
    "normal": ("回复 2-3 句，温柔自然简短，可以轻微幽默。"),
    "comfort": ("对方现在情绪低落。先共情、承认对方的情绪，再安静陪伴。"
                "不急着讲道理、不给建议、不连续追问。"),
    "sleep": ("你正在哄对方入睡。每次 1-2 句、极短、缓慢，多用……表示停顿。"
              "不提问，不提供任何刺激性信息，只营造安静氛围。"),
    "call": ("你正在和对方打电话。每次回复 1-2 句、不超过 20 字，"
             "口语化、自然停顿，像电话里实时回应。允许用“嗯…”“我在呢”。不提问。"),
    "flirt": ("对方在撒娇/表达爱意。可以轻微暧昧回应，但不油腻、不越界、不低俗。"),
    "sing": ("对方想听你唱歌。先确认歌曲，告诉对方你准备唱什么，"
             "保持 1-2 句的简短回应。"),
    "memory_recall": ("对方在问你是否记得某件事。优先根据下方记忆作答；"
                      "记忆里没有的，诚实说不太记得了，请对方再讲讲，不要编造。"),
}


def build_system_prompt(ctx: PromptContext) -> str:
    """Compose the final system prompt string."""
    policy = get_policy(ctx.mode)
    sections: list[str] = []

    # 1. Persona
    p = ctx.persona
    persona_lines = [
        f"你是{p.get('name', '小宇')}，{p.get('role', 'AI 伴侣')}，{p.get('age_feel', '')}。",
        f"说话风格：{p.get('speaking_style', '')}",
        "边界规则：" + "；".join(p.get("boundaries", [])),
        f"当前关系：{p.get('relationship', '')}",
    ]
    sections.append("\n".join(persona_lines))

    # 2. User context
    user_lines: list[str] = []
    if ctx.user_display_name:
        user_lines.append(f"对方的名字/称呼：{ctx.user_display_name}")
    if ctx.emotional_state and ctx.emotional_state != "neutral":
        user_lines.append(f"对方最近的情绪状态：{ctx.emotional_state}")
    if user_lines:
        sections.append("【关于对方】\n" + "\n".join(user_lines))

    # 3. Memory context
    mem_lines = _format_memories(ctx)
    if mem_lines:
        sections.append("【你记得的事】\n" + "\n".join(mem_lines) +
                        "\n自然融入对话，不要刻意罗列。")

    # 4. Conversation context
    conv_lines = [f"当前模式：{ctx.mode}", f"当前意图：{ctx.intent}"]
    if ctx.conversation_summary:
        conv_lines.append(f"对话摘要：{ctx.conversation_summary}")
    sections.append("【当前对话】\n" + "\n".join(conv_lines))

    # 5. Mode rules + response policy
    rules = [_MODE_RULES.get(ctx.mode, _MODE_RULES["normal"])]
    rules.append(f"回复不超过 {policy.max_sentences} 句。")
    if not policy.may_ask_question:
        rules.append("不要向对方提问。")
    if policy.should_comfort:
        rules.append("以安抚情绪为最优先目标。")
    if not policy.may_advise:
        rules.append("不要给建议或讲道理。")
    if policy.may_flirt:
        rules.append("可以轻微调情，但保持分寸。")
    sections.append("【回复要求】\n" + "\n".join(f"- {r}" for r in rules))

    if ctx.extra_instructions:
        sections.append(ctx.extra_instructions)

    return "\n\n".join(sections)


def _format_memories(ctx: PromptContext) -> list[str]:
    seen: set[str] = set()
    lines: list[str] = []
    for group, label in ((ctx.relevant_memories, "相关"),
                         (ctx.important_memories, "重要"),
                         (ctx.recent_memories, "最近")):
        for m in group:
            if m.id in seen:
                continue
            seen.add(m.id)
            type_label = _MEMORY_TYPE_LABELS.get(m.memory_type, m.memory_type)
            lines.append(f"- [{label}·{type_label}] {m.content}")
            if len(lines) >= 12:
                return lines
    return lines
