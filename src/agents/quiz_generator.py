from __future__ import annotations

import random
import re
from datetime import datetime
from typing import Any


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
                "تجاوز الأمثلة والانتقال لأسئلة غير مرتبطة.",
                "التركيز فقط على شكل الملاحظات.",
            ],
            "explanation": "التعريف الواضح مع مثال يختبر الحفظ والفهم معا.",
        },
        {
            "question": "ما النشاط الذي يثبت أنك فهمت {topic}؟",
            "correct": "حل مسألة جديدة وشرح كل خطوة بكلماتك.",
            "distractors": [
                "إعادة قراءة نفس الفقرة بدون اختبار نفسك.",
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

    def generate(
        self,
        topic: str,
        count: int = 5,
        *,
        context_chunks: list[dict[str, Any]] | None = None,
        language: str = "en",
    ) -> dict[str, Any]:
        clean_topic = self._clean_topic(topic)
        question_count = min(max(int(count or 1), 1), 10)
        context_chunks = context_chunks or []
        rng = random.Random(f"{clean_topic.lower()}::{question_count}::{language}")

        questions = self._context_questions(
            topic=clean_topic,
            context_chunks=context_chunks,
            limit=question_count,
            language=language,
            rng=rng,
        )

        templates = self.GENERIC_ARABIC_TEMPLATES if language == "ar" else self.GENERIC_ENGLISH_TEMPLATES
        template_index = 0
        while len(questions) < question_count:
            template = templates[template_index % len(templates)]
            questions.append(self._template_question(template, clean_topic, len(questions) + 1, rng))
            template_index += 1

        flashcards = self._flashcards(clean_topic, context_chunks=context_chunks, language=language)
        quiz = {
            "topic": clean_topic,
            "language": language,
            "questions": questions,
            "flashcards": flashcards,
            "source_count": len(context_chunks),
            "generated_at_utc": datetime.utcnow().isoformat(timespec="seconds"),
        }

        return {
            "ok": True,
            "status": "generated",
            "message": "Quiz generated.",
            "topic": clean_topic,
            "count": len(questions),
            "quiz": quiz,
            "questions": questions,
            "flashcards": flashcards,
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
                prompt = "What do my notes say?" if language != "ar" else "ماذا تقول ملاحظاتي؟"
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
