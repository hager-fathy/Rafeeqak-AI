"""Translate study-plan fields and recommendation text for chat responses."""

from __future__ import annotations

import re
from typing import Any

from src.localization import normalize_language, t

_LECTURE_PATTERN = re.compile(r"^lecture\s+(\d+)\s*$", re.IGNORECASE)
_LECTURES_RANGE_PATTERN = re.compile(r"^lectures\s+(\d+)\s*-\s*(\d+)\s*$", re.IGNORECASE)

_ARABIC_LECTURE_ORDINALS: dict[int, str] = {
    1: "الأولى",
    2: "الثانية",
    3: "الثالثة",
    4: "الرابعة",
    5: "الخامسة",
    6: "السادسة",
}

_PHASE_LABELS_EN_TO_AR: dict[str, str] = {
    "recovery session": "جلسة تعويض",
    "concept review": "مراجعة المفاهيم",
    "weak-topic practice": "تدريب على نقاط الضعف",
    "mixed review": "مراجعة متنوعة",
    "checkpoint quiz": "اختبار قصير",
    "final review": "مراجعة نهائية",
}

_PHASE_KEYS_TO_AR: dict[str, str] = {
    "recovery": "جلسة تعويض",
    "foundation": "مراجعة المفاهيم",
    "deep_practice": "تدريب على نقاط الضعف",
    "mixed_review": "مراجعة متنوعة",
    "checkpoint": "اختبار قصير",
    "final_review": "مراجعة نهائية",
}

_TASK_PHRASES_EN_TO_AR: list[tuple[str, str]] = [
    (
        "Take a checkpoint quiz on {topic}, review wrong answers, and update weak points before moving on.",
        "حل اختبار قصير على {topic}، ثم مراجعة الإجابات الخاطئة وتحديث نقاط الضعف قبل الانتقال للموضوع التالي.",
    ),
    (
        "Review the core ideas of {topic}, list key formulas or definitions, and solve one guided example.",
        "راجع الأفكار الأساسية لـ{topic}، اكتب أهم الصيغ أو التعريفات، وحل مثالاً موجهاً واحداً.",
    ),
    (
        "Practice {topic} with new problems, explain each step aloud, and log any repeated mistakes.",
        "تدرّب على {topic} بمسائل جديدة، اشرح كل خطوة بصوت عالٍ، وسجّل الأخطاء المتكررة.",
    ),
    (
        "Mix {topic} with earlier topics, compare problem types, and write a quick exam-style checklist.",
        "امزج {topic} مع موضوعات سابقة، قارن أنواع المسائل، واكتب قائمة مراجعة سريعة بأسلوب الامتحان.",
    ),
    (
        "Do a final review of {topic}, focus on high-yield mistakes, and prepare a one-page recall sheet.",
        "نفّذ مراجعة نهائية لـ{topic}، ركّز على الأخطاء الأكثر أهمية، وأعد صفحة مراجعة واحدة.",
    ),
    (
        "Recover the delayed work for {topic}, write a compressed summary, and reschedule any unfinished sub-parts.",
        "عوّض العمل المتأخر لـ{topic}، اكتب ملخصاً مضغوطاً، وأعد جدولة الأجزاء غير المكتملة.",
    ),
]

_TIME_NOTES_EN_TO_AR: list[tuple[str, str]] = [
    (
        "Split the session between review, practice, and a short written summary.",
        "اقسِم وقتك بين المراجعة، التدريب، وكتابة ملخص قصير.",
    ),
    (
        "Keep this compact: one focused pass and five recall questions.",
        "اجعلها مركزة: جولة مراجعة واحدة وخمسة أسئلة استرجاع.",
    ),
    (
        "Use the extra time for worked examples, active recall, and a short self-test.",
        "استخدم الوقت الإضافي في أمثلة محلولة، استرجاع نشط، واختبار ذاتي قصير.",
    ),
]

_SUFFIX_PHRASES_EN_TO_AR: list[tuple[str, str]] = [
    (" Prioritize mistake patterns because this is marked as a weak topic.", " أعطِ أولوية لأنماط الأخطاء لأن هذا موضوع ضعف."),
    (" Cover {slot} first.", " ابدأ بـ{slot} أولاً."),
    (" Keep the pace light and focus on accuracy.", " اجعل الإيقاع خفيفاً وركّز على الدقة."),
    (" Keep the session balanced between explanation and practice.", " وازِن بين الشرح والتدريب."),
    (" Add one timed exam-style question before you finish.", " أضف سؤالاً واحداً بأسلوب الامتحان مع مؤقت قبل الإنهاء."),
    ("Recover the missed work first, then close with a short self-test.", "عوّض العمل الفائت أولاً، ثم اختم باختبار ذاتي قصير."),
    ("Use one compact catch-up block and keep the notes minimal.", "استخدم كتلة تعويض مركزة واجعل الملاحظات مختصرة."),
]


def localize_planner_topic(topic: str, language: str | None) -> str:
    language = normalize_language(language)
    raw = str(topic or "").strip()
    if not raw or language != "ar":
        return raw

    lecture_match = _LECTURE_PATTERN.match(raw)
    if lecture_match:
        number = int(lecture_match.group(1))
        ordinal = _ARABIC_LECTURE_ORDINALS.get(number)
        if ordinal:
            return f"المحاضرة {ordinal}"
        return f"المحاضرة رقم {number}"

    range_match = _LECTURES_RANGE_PATTERN.match(raw)
    if range_match:
        start = int(range_match.group(1))
        end = int(range_match.group(2))
        start_label = localize_planner_topic(f"Lecture {start}", language)
        end_label = localize_planner_topic(f"Lecture {end}", language)
        return f"{start_label} إلى {end_label}"

    return raw


def localize_planner_phase(phase: str, language: str | None) -> str:
    language = normalize_language(language)
    raw = str(phase or "").strip()
    if not raw or language != "ar":
        return raw

    key = raw.casefold().replace(" ", "_").replace("-", "_")
    if key in _PHASE_KEYS_TO_AR:
        return _PHASE_KEYS_TO_AR[key]

    lowered = raw.casefold()
    return _PHASE_LABELS_EN_TO_AR.get(lowered, raw)


def localize_planner_topics(topics: list[str], language: str | None) -> str:
    return "، ".join(localize_planner_topic(topic, language) for topic in topics if str(topic).strip())


def localize_planner_task_text(
    task_text: str,
    language: str | None,
    *,
    topic: str | None = None,
) -> str:
    language = normalize_language(language)
    raw = " ".join(str(task_text or "").split())
    if not raw or language != "ar":
        return raw

    localized_topic = localize_planner_topic(topic or "", language)
    normalized = raw

    for english_template, arabic_template in _TASK_PHRASES_EN_TO_AR:
        english_filled = english_template.format(topic=topic or localized_topic)
        if normalized.startswith(english_filled):
            remainder = normalized[len(english_filled) :].strip()
            arabic_base = arabic_template.format(topic=localized_topic)
            if not remainder:
                return arabic_base
            normalized = f"{arabic_base} {remainder}"
            break

    for english, arabic in _TIME_NOTES_EN_TO_AR:
        normalized = normalized.replace(english, arabic)

    cover_match = re.search(r"Cover (Lectures?\s+[\d\-]+) first\.", normalized, re.IGNORECASE)
    if cover_match:
        slot_raw = cover_match.group(1).strip()
        if slot_raw.lower().startswith("lectures "):
            start, end = slot_raw.split()[-1].split("-")
            slot_label = (
                f"{localize_planner_topic(f'Lecture {start}', language)} "
                f"إلى {localize_planner_topic(f'Lecture {end}', language)}"
            )
        else:
            slot_label = localize_planner_topic(slot_raw, language)
        normalized = re.sub(
            r"Cover (Lectures?\s+[\d\-]+) first\.",
            f"ابدأ بـ{slot_label} أولاً.",
            normalized,
            flags=re.IGNORECASE,
        )

    for english_template, arabic_template in _SUFFIX_PHRASES_EN_TO_AR:
        if "{slot}" in english_template:
            continue
        normalized = normalized.replace(english_template, arabic_template)

    normalized = _replace_embedded_english_terms(normalized)
    return " ".join(normalized.split())


def _replace_embedded_english_terms(text: str) -> str:
    replacements = [
        ("review wrong answers", "مراجعة الإجابات الخاطئة"),
        ("update weak points", "تحديث نقاط الضعف"),
        ("weak points", "نقاط الضعف"),
        ("weak topics", "نقاط الضعف"),
        ("weak topic", "نقطة ضعف"),
        ("checkpoint quiz", "اختبار قصير"),
        ("Concept review", "مراجعة المفاهيم"),
        ("Weak-topic practice", "تدريب على نقاط الضعف"),
        ("Mixed review", "مراجعة متنوعة"),
        ("Final review", "مراجعة نهائية"),
        ("Recovery session", "جلسة تعويض"),
    ]
    updated = text
    for english, arabic in replacements:
        updated = re.sub(re.escape(english), arabic, updated, flags=re.IGNORECASE)
    for match in _LECTURE_PATTERN.finditer(updated):
        updated = updated.replace(match.group(0), localize_planner_topic(match.group(0), "ar"))
    return updated


def format_study_recommendation(task: dict[str, Any], language: str | None) -> str:
    language = normalize_language(language)
    topic = localize_planner_topic(str(task.get("topic") or ""), language)
    hours = task.get("hours", 0)
    goal = localize_planner_task_text(
        str(task.get("task") or ""),
        language,
        topic=str(task.get("topic") or ""),
    )

    checkpoint_note = ""
    if task.get("checkpoint") or task.get("quiz_required"):
        if language == "ar" and "اختبار" not in goal:
            checkpoint_note = t("agent.planner.checkpoint", language)
        elif language != "ar":
            checkpoint_note = t("agent.planner.checkpoint", language)

    return t(
        "agent.planner.today",
        language,
        topic=topic,
        hours=hours,
        goal=goal,
        checkpoint_note=checkpoint_note,
    )


def format_priority_explanation(active_plan: dict[str, Any], language: str | None) -> str:
    language = normalize_language(language)
    weak_topics = [str(topic).strip() for topic in active_plan.get("weak_topics", []) if str(topic).strip()]
    if not weak_topics:
        return t("agent.planner.no_weak", language)
    topics = localize_planner_topics(weak_topics, language)
    return t("agent.planner.priorities", language, topics=topics)


def contains_english_planner_terms(text: str) -> bool:
    lowered = str(text or "").casefold()
    markers = (
        "lecture ",
        "checkpoint quiz",
        "weak points",
        "weak topics",
        "review wrong answers",
        "concept review",
        "today focus",
        "goal:",
    )
    return any(marker in lowered for marker in markers)
