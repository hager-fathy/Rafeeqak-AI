from __future__ import annotations

import random
import re
from datetime import datetime
from typing import Any

from src.localization import normalize_language, t
from src.prompts import render_prompt
from src.tools.llm_client import LLMClient


class QuizGeneratorAgent:
    """Generates deterministic topic quizzes and flashcards for revision."""

    GENERIC_ENGLISH_TEMPLATES = [
        {
            "question": "What is the best first step when revising {topic}?",
            "correct": "Define the core idea, then connect it to a worked example.",
            "distractors": [
                "Memorize only the title of the topic.",
                "Skip examples and go straight to unrelated questions.",
                "Focus only on formatting notes.",
            ],
            "explanation": "A clear definition plus an example checks both recall and understanding.",
        },
        {
            "question": "Which activity best proves that you understand {topic}?",
            "correct": "Solving a new problem and explaining each step in your own words.",
            "distractors": [
                "Rereading the same paragraph without testing yourself.",
                "Only highlighting definitions.",
                "Avoiding mistakes by not practicing.",
            ],
            "explanation": "Transfer to a new problem is stronger evidence of mastery than rereading.",
        },
        {
            "question": "What should you do after missing a question about {topic}?",
            "correct": "Identify the misconception, review the relevant note, and retry a similar question.",
            "distractors": [
                "Ignore the mistake and move to a random topic.",
                "Delete the question from the revision list.",
                "Assume the whole course is too difficult.",
            ],
            "explanation": "Targeted correction turns a wrong answer into a weak-topic signal.",
        },
        {
            "question": "How should {topic} appear in a strong study plan?",
            "correct": "As focused practice blocks with short checkpoints.",
            "distractors": [
                "Only as one long passive reading session.",
                "Only after the exam date.",
                "As a task with no success criteria.",
            ],
            "explanation": "Short checkpoints make progress measurable and easier to adapt.",
        },
        {
            "question": "Which revision note is most useful for {topic}?",
            "correct": "A brief summary with formulas, assumptions, and one solved example.",
            "distractors": [
                "A copied paragraph with no structure.",
                "A list of unrelated course names.",
                "A blank page marked as completed.",
            ],
            "explanation": "Useful revision notes make the concept, constraints, and application visible.",
        },
    ]

    GENERIC_ARABIC_TEMPLATES = [
        {
            "question": "ما أفضل خطوة أولى عند مراجعة {topic}؟",
            "correct": "فهم الفكرة الأساسية ثم ربطها بمثال محلول.",
            "distractors": [
                "حفظ عنوان الموضوع فقط.",
                "تجاوز الأمثلة والانتقال إلى أسئلة غير مرتبطة.",
                "التركيز فقط على شكل الملاحظات.",
            ],
            "explanation": "التعريف الواضح مع مثال يختبر الحفظ والفهم معا.",
        },
        {
            "question": "ما النشاط الذي يثبت أنك فهمت {topic}؟",
            "correct": "حل مسألة جديدة وشرح كل خطوة بكلماتك.",
            "distractors": [
                "إعادة قراءة نفس الفقرة دون اختبار نفسك.",
                "تظليل التعريفات فقط.",
                "تجنب التدريب حتى لا تخطئ.",
            ],
            "explanation": "تطبيق الفكرة على مسألة جديدة أقوى من مجرد القراءة.",
        },
        {
            "question": "ماذا تفعل بعد إجابة خاطئة في {topic}؟",
            "correct": "تحدد سبب الخطأ، تراجع الملاحظة المناسبة، ثم تعيد سؤالا مشابها.",
            "distractors": [
                "تتجاهل الخطأ وتنتقل لموضوع عشوائي.",
                "تحذف السؤال من قائمة المراجعة.",
                "تفترض أن كل المقرر صعب.",
            ],
            "explanation": "تصحيح الخطأ يحوله إلى إشارة واضحة لنقطة ضعف.",
        },
    ]

    def __init__(self, *, llm_client: LLMClient | None = None) -> None:
        self.llm_client = llm_client or LLMClient()

    def generate(
        self,
        topic: str,
        count: int = 5,
        *,
        context_chunks: list[dict[str, Any]] | None = None,
        language: str = "en",
        difficulty: str = "medium",
        question_types: list[str] | None = None,
        previous_questions: list[str] | None = None,
    ) -> dict[str, Any]:
        language = normalize_language(language)
        clean_topic = self._clean_topic(topic)
        question_count = max(int(count or 1), 1)
        context_chunks = context_chunks or []
        selected_types = self._normalize_question_types(question_types)
        previous_normalized = {self._normalize_text(item) for item in previous_questions or []}
        rng = random.Random(
            f"{clean_topic.lower()}::{question_count}::{language}::{difficulty.lower()}::"
            f"{','.join(selected_types)}::{len(previous_normalized)}"
        )

        llm_quiz = self._generate_with_llm(
            topic=clean_topic,
            count=question_count,
            context_chunks=context_chunks,
            language=language,
            difficulty=difficulty,
            question_types=selected_types,
        )
        if llm_quiz:
            questions = llm_quiz["questions"]
            flashcards = llm_quiz["flashcards"]
            generation_mode = "llm"
        else:
            questions = self._offline_questions(
                topic=clean_topic,
                count=question_count,
                language=language,
                difficulty=difficulty,
                question_types=selected_types,
                previous_normalized=previous_normalized,
                context_chunks=context_chunks,
                rng=rng,
            )
            flashcards = self._flashcards(clean_topic, context_chunks=context_chunks, language=language)
            generation_mode = "offline_template"

        quiz = {
            "topic": clean_topic,
            "language": language,
            "difficulty": difficulty,
            "question_types": selected_types,
            "questions": questions,
            "flashcards": flashcards,
            "source_count": len(context_chunks),
            "generated_at_utc": datetime.utcnow().isoformat(timespec="seconds"),
            "generation_mode": generation_mode,
        }

        return {
            "ok": True,
            "status": "generated",
            "message": t("quiz.generated", language, source_note=""),
            "topic": clean_topic,
            "count": len(questions),
            "quiz": quiz,
            "questions": questions,
            "flashcards": flashcards,
            "generation_mode": generation_mode,
        }

    def infer_topic(self, message: str, *, fallback: str = "Revision") -> str:
        cleaned = message.strip()
        patterns = [
            r"(?:quiz me on|test me on|questions on|practice)\s+(.+)",
            r"(?:اختبرني في|اختبرني على|أسئلة عن|اسئلة عن|كويز عن)\s+(.+)",
        ]
        for pattern in patterns:
            match = re.search(pattern, cleaned, flags=re.IGNORECASE)
            if match:
                return self._clean_topic(match.group(1))
        return self._clean_topic(fallback)

    def _context_questions(
        self,
        *,
        topic: str,
        context_chunks: list[dict[str, Any]],
        limit: int,
        language: str,
        rng: random.Random,
    ) -> list[dict[str, Any]]:
        questions = []
        for chunk in context_chunks[:limit]:
            text = self._trim(chunk.get("text", ""), max_length=180)
            if not text:
                continue
            source = chunk.get("source_name") or chunk.get("source") or "uploaded notes"
            section = chunk.get("section") or "section"
            if language == "ar":
                question = f"أي عبارة تدعمها ملاحظاتك عن {topic}؟"
                distractors = [
                    "الملخص لا يحتوي على أي فكرة مرتبطة بالموضوع.",
                    "أفضل طريقة للمراجعة هي تجاهل الأمثلة بالكامل.",
                    "لا توجد حاجة لاختبار الفهم بعد القراءة.",
                ]
                explanation = f"الإجابة مأخوذة من {source} ({section})."
            else:
                question = f"Which statement is supported by your notes about {topic}?"
                distractors = [
                    "The notes do not contain any idea related to the topic.",
                    "The best revision method is to ignore examples completely.",
                    "There is no need to test understanding after reading.",
                ]
                explanation = f"This answer is grounded in {source} ({section})."
            options, answer_index = self._shuffle_options(text, distractors, rng)
            questions.append(
                {
                    "id": f"context-{len(questions) + 1}",
                    "type": "mcq",
                    "topic": topic,
                    "question": question,
                    "options": options,
                    "answer_index": answer_index,
                    "explanation": explanation,
                    "source": f"{source} ({section})",
                }
            )
        return questions

    def _offline_questions(
        self,
        *,
        topic: str,
        count: int,
        language: str,
        difficulty: str,
        question_types: list[str],
        previous_normalized: set[str],
        context_chunks: list[dict[str, Any]],
        rng: random.Random,
    ) -> list[dict[str, Any]]:
        questions: list[dict[str, Any]] = []
        templates = self.GENERIC_ARABIC_TEMPLATES if language == "ar" else self.GENERIC_ENGLISH_TEMPLATES
        type_index = 0
        template_index = 0
        attempts = 0
        while len(questions) < count and attempts < count * 8:
            question_type = question_types[type_index % len(question_types)]
            template = templates[template_index % len(templates)]
            context_chunk = context_chunks[template_index % len(context_chunks)] if context_chunks else None
            question = self._question_for_type(
                question_type=question_type,
                template=template,
                topic=topic,
                question_number=len(questions) + 1,
                rng=rng,
                language=language,
                difficulty=difficulty,
                context_chunk=context_chunk,
            )
            normalized = self._normalize_text(question["question"])
            if normalized not in previous_normalized or attempts >= count * 4:
                if normalized in previous_normalized:
                    question["question"] = f"{question['question']} (variant {len(questions) + 1})"
                questions.append(question)
                previous_normalized.add(self._normalize_text(question["question"]))
            type_index += 1
            template_index += 1
            attempts += 1
        return questions

    def _question_for_type(
        self,
        *,
        question_type: str,
        template: dict[str, Any],
        topic: str,
        question_number: int,
        rng: random.Random,
        language: str,
        difficulty: str,
        context_chunk: dict[str, Any] | None,
    ) -> dict[str, Any]:
        if question_type == "true_false":
            return self._true_false_question(template, topic, question_number, rng, language, difficulty)
        if question_type == "short_answer":
            return self._short_answer_question(template, topic, question_number, language, difficulty, context_chunk)
        if question_type == "matching":
            return self._matching_question(template, topic, question_number, language, difficulty)
        if context_chunk:
            return self._context_questions(
                topic=topic,
                context_chunks=[context_chunk],
                limit=1,
                language=language,
                rng=rng,
            )[0]
        return self._template_question(template, topic, question_number, rng)

    def _true_false_question(
        self,
        template: dict[str, Any],
        topic: str,
        question_number: int,
        rng: random.Random,
        language: str,
        difficulty: str,
    ) -> dict[str, Any]:
        use_correct = rng.choice([True, False])
        statement = template["correct"] if use_correct else template["distractors"][0]
        question_text = (
            f"صح أم خطأ ({difficulty}): {statement}"
            if language == "ar"
            else f"True or false ({difficulty}): {statement}"
        )
        return {
            "id": f"true-false-{question_number}",
            "type": "true_false",
            "topic": topic,
            "difficulty": difficulty,
            "question": question_text,
            "options": ["صح", "خطأ"] if language == "ar" else ["True", "False"],
            "answer_index": 0 if use_correct else 1,
            "explanation": template["explanation"],
            "source": "generated",
        }

    def _short_answer_question(
        self,
        template: dict[str, Any],
        topic: str,
        question_number: int,
        language: str,
        difficulty: str,
        context_chunk: dict[str, Any] | None,
    ) -> dict[str, Any]:
        expected = self._trim(context_chunk.get("text", ""), max_length=180) if context_chunk else template["correct"]
        keywords = self._keywords(expected, topic)
        prompt = (
            f"إجابة قصيرة ({difficulty}): اشرح {topic} في جملة أو جملتين."
            if language == "ar"
            else f"Short answer ({difficulty}): Explain {topic} in one or two sentences."
        )
        return {
            "id": f"short-answer-{question_number}",
            "type": "short_answer",
            "topic": topic,
            "difficulty": difficulty,
            "question": prompt,
            "expected_answer": expected,
            "keywords": keywords,
            "explanation": template["explanation"],
            "source": (
                f"{context_chunk.get('source_name', 'uploaded notes')} ({context_chunk.get('section', 'section')})"
                if context_chunk
                else "generated"
            ),
        }

    def _matching_question(
        self,
        template: dict[str, Any],
        topic: str,
        question_number: int,
        language: str,
        difficulty: str,
    ) -> dict[str, Any]:
        if language == "ar":
            pairs = [
                {"left": f"الفكرة الأساسية في {topic}", "right": template["correct"]},
                {"left": f"خطأ شائع في {topic}", "right": template["distractors"][0]},
                {"left": f"حركة تدريب في {topic}", "right": "استخدم مثالا محلولا ثم حل سؤالا جديدا."},
            ]
            question = f"مطابقة ({difficulty}): طابق كل عبارة عن {topic} مع الوصف الأنسب."
        else:
            pairs = [
                {"left": f"{topic} core idea", "right": template["correct"]},
                {"left": f"{topic} common trap", "right": template["distractors"][0]},
                {"left": f"{topic} practice move", "right": "Use a worked example, then solve a new question."},
            ]
            question = f"Matching ({difficulty}): Match each {topic} prompt to the best description."
        return {
            "id": f"matching-{question_number}",
            "type": "matching",
            "topic": topic,
            "difficulty": difficulty,
            "question": question,
            "pairs": pairs,
            "options": [pair["right"] for pair in pairs],
            "answer_map": {pair["left"]: pair["right"] for pair in pairs},
            "explanation": template["explanation"],
            "source": "generated",
        }

    def _generate_with_llm(
        self,
        *,
        topic: str,
        count: int,
        context_chunks: list[dict[str, Any]],
        language: str,
        difficulty: str,
        question_types: list[str],
    ) -> dict[str, Any] | None:
        if not self.llm_client.is_available or question_types != ["mcq"]:
            return None

        source_text = "\n\n".join(
            f"Source: {chunk.get('source_name', 'uploaded notes')} ({chunk.get('section', 'section')})\n"
            f"{self._trim(chunk.get('text', ''), max_length=700)}"
            for chunk in context_chunks[:5]
            if self._trim(chunk.get("text", ""), max_length=700)
        )
        if not source_text:
            source_text = "No uploaded material excerpts were retrieved. Generate from the topic only."

        response_language = "Arabic" if language == "ar" else "English"
        prompt = render_prompt(
            "quiz_generation",
            course_name=self._course_name_from_context(context_chunks),
            topic=topic,
            difficulty=difficulty,
            number_of_questions=count,
            question_types=", ".join(question_types),
            context=source_text,
            language=response_language,
        )

        try:
            payload = self.llm_client.generate_json(
                system_prompt=prompt.system,
                user_prompt=prompt.user,
                temperature=0.4,
                max_tokens=1600,
            )
        except Exception:
            return None
        if not payload:
            return None

        questions = self._normalize_llm_questions(payload.get("questions"), topic=topic, count=count)
        if len(questions) != count:
            return None
        flashcards = self._normalize_llm_flashcards(payload.get("flashcards"))
        if not flashcards:
            flashcards = self._flashcards(topic, context_chunks=context_chunks, language=language)
        return {"questions": questions, "flashcards": flashcards}

    def _normalize_llm_questions(self, raw_questions: Any, *, topic: str, count: int) -> list[dict[str, Any]]:
        if not isinstance(raw_questions, list):
            return []

        questions = []
        for index, item in enumerate(raw_questions[:count], start=1):
            if not isinstance(item, dict):
                continue
            options = item.get("options")
            answer_index = item.get("answer_index")
            if not isinstance(options, list) or len(options) != 4:
                continue
            try:
                answer_index = int(answer_index)
            except (TypeError, ValueError):
                continue
            if answer_index not in range(4):
                continue
            question_text = str(item.get("question") or "").strip()
            if not question_text:
                continue
            questions.append(
                {
                    "id": f"llm-{index}",
                    "type": "mcq",
                    "topic": topic,
                    "question": question_text,
                    "options": [str(option).strip() for option in options],
                    "answer_index": answer_index,
                    "explanation": str(item.get("explanation") or "").strip(),
                    "source": str(item.get("source") or "llm").strip(),
                }
            )
        return questions

    def _course_name_from_context(self, context_chunks: list[dict[str, Any]]) -> str:
        for chunk in context_chunks:
            course_name = str(chunk.get("course_name") or "").strip()
            if course_name:
                return course_name
        return "Active course"

    def _normalize_llm_flashcards(self, raw_flashcards: Any) -> list[dict[str, str]]:
        if not isinstance(raw_flashcards, list):
            return []
        flashcards = []
        for item in raw_flashcards[:6]:
            if not isinstance(item, dict):
                continue
            front = str(item.get("front") or "").strip()
            back = str(item.get("back") or "").strip()
            if front and back:
                flashcards.append({"front": front, "back": back})
        return flashcards

    def _template_question(
        self,
        template: dict[str, Any],
        topic: str,
        question_number: int,
        rng: random.Random,
    ) -> dict[str, Any]:
        options, answer_index = self._shuffle_options(template["correct"], template["distractors"], rng)
        return {
            "id": f"template-{question_number}",
            "type": "mcq",
            "topic": topic,
            "question": template["question"].format(topic=topic),
            "options": options,
            "answer_index": answer_index,
            "explanation": template["explanation"],
            "source": "generated",
        }

    def _flashcards(
        self,
        topic: str,
        *,
        context_chunks: list[dict[str, Any]],
        language: str,
    ) -> list[dict[str, str]]:
        if language == "ar":
            cards = [
                {"front": f"ما الفكرة الأساسية في {topic}؟", "back": "اكتب تعريفا قصيرا ثم اربطه بمثال."},
                {"front": f"كيف تختبر فهمك في {topic}؟", "back": "حل سؤالا جديدا واشرح خطوات الحل."},
            ]
        else:
            cards = [
                {"front": f"What is the core idea of {topic}?", "back": "Write a short definition and connect it to an example."},
                {"front": f"How do you test mastery of {topic}?", "back": "Solve a new question and explain the steps."},
            ]

        if context_chunks:
            best_chunk = self._trim(context_chunks[0].get("text", ""), max_length=220)
            if best_chunk:
                prompt = "ماذا تقول ملاحظاتي؟" if language == "ar" else "What do my notes say?"
                cards.insert(0, {"front": f"{prompt} {topic}", "back": best_chunk})
        return cards

    def _shuffle_options(
        self,
        correct: str,
        distractors: list[str],
        rng: random.Random,
    ) -> tuple[list[str], int]:
        options = [correct, *distractors[:3]]
        rng.shuffle(options)
        return options, options.index(correct)

    def _clean_topic(self, topic: str) -> str:
        cleaned = re.sub(r"\s+", " ", str(topic or "").strip(" .؟?؛:"))
        return cleaned or "Revision"

    def _trim(self, text: str, *, max_length: int) -> str:
        compact = " ".join(str(text or "").split())
        if len(compact) <= max_length:
            return compact
        return f"{compact[:max_length].rsplit(' ', 1)[0].rstrip()}..."

    def _normalize_question_types(self, question_types: list[str] | None) -> list[str]:
        allowed = {"mcq", "true_false", "short_answer", "matching"}
        normalized = [str(item).strip().lower() for item in question_types or ["mcq"]]
        selected = [item for item in normalized if item in allowed]
        return selected or ["mcq"]

    def _normalize_text(self, text: str) -> str:
        return re.sub(r"\s+", " ", str(text or "").strip().lower())

    def _keywords(self, text: str, topic: str) -> list[str]:
        tokens = re.findall(r"[\w\u0600-\u06FF]+", f"{topic} {text}".lower())
        stopwords = {"the", "and", "that", "with", "from", "this", "your", "about", "then", "only"}
        keywords = []
        for token in tokens:
            if len(token) < 4 or token in stopwords or token in keywords:
                continue
            keywords.append(token)
            if len(keywords) == 6:
                break
        return keywords
