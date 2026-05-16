from __future__ import annotations

import random
import re
from datetime import datetime
from typing import Any

from src.localization import normalize_language, t
from src.prompts import render_prompt
from src.tools.llm_client import LLMClient
from src.tools.quiz_history import normalize_question_text


class QuizGeneratorAgent:
    """Generates deterministic topic quizzes and flashcards for revision."""

    MAX_QUESTION_COUNT = 20
    ALLOWED_DIFFICULTIES = {"easy", "medium", "hard"}
    ALLOWED_QUESTION_TYPES = {"mcq", "true_false", "short_answer", "matching"}

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
        avoid_questions: list[str] | None = None,
    ) -> dict[str, Any]:
        language = normalize_language(language)
        clean_topic = self._clean_topic(topic)
        question_count = self._coerce_count(count)
        difficulty = self._normalize_difficulty(difficulty)
        context_chunks = self._prepare_context_chunks(context_chunks or [])
        selected_types = self._normalize_question_types(question_types)
        avoid_question_texts = [
            str(item)
            for item in [*(avoid_questions or []), *(previous_questions or [])]
            if str(item or "").strip()
        ]
        previous_normalized = {normalize_question_text(item) for item in avoid_question_texts}
        previous_normalized.discard("")
        rng = random.Random(
            f"{clean_topic.lower()}::{question_count}::{language}::{difficulty}::"
            f"{','.join(selected_types)}::{len(previous_normalized)}"
        )

        llm_quiz = self._generate_with_llm(
            topic=clean_topic,
            count=question_count,
            context_chunks=context_chunks,
            language=language,
            difficulty=difficulty,
            question_types=selected_types,
            avoid_questions=avoid_question_texts,
            previous_normalized=previous_normalized,
            rng=rng,
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

        limited_material = len(questions) < question_count
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
            "limited_material": limited_material,
            "requested_count": question_count,
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
            "limited_material": limited_material,
            "requested_count": question_count,
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
        used_normalized = set(previous_normalized)
        candidate_normalized: set[str] = set()
        context_options = context_chunks or [None]
        stem_count = 4
        max_attempts = len(question_types) * len(templates) * len(context_options) * stem_count
        start_offset = len(previous_normalized)

        for attempt in range(max_attempts):
            if len(questions) >= count:
                break
            question_type = question_types[(start_offset + attempt) % len(question_types)]
            template = templates[((start_offset // max(1, len(question_types))) + attempt) % len(templates)]
            context_chunk = context_options[
                ((start_offset // max(1, len(templates))) + attempt) % len(context_options)
            ]
            variant_index = (start_offset + attempt) % stem_count
            question = self._question_for_type(
                question_type=question_type,
                template=template,
                topic=topic,
                question_number=len(questions) + 1,
                rng=rng,
                language=language,
                difficulty=difficulty,
                context_chunk=context_chunk,
                variant_index=variant_index,
            )
            normalized = normalize_question_text(question["question"])
            if not normalized or normalized in candidate_normalized:
                continue
            candidate_normalized.add(normalized)
            if normalized not in used_normalized:
                questions.append(question)
                used_normalized.add(normalized)
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
        variant_index: int,
    ) -> dict[str, Any]:
        if question_type == "true_false":
            return self._true_false_question(template, topic, question_number, rng, language, difficulty, variant_index)
        if question_type == "short_answer":
            return self._short_answer_question(
                template,
                topic,
                question_number,
                language,
                difficulty,
                context_chunk,
                variant_index,
            )
        if question_type == "matching":
            return self._matching_question(template, topic, question_number, language, difficulty, variant_index)
        if context_chunk:
            return self._context_question(
                topic=topic,
                context_chunk=context_chunk,
                question_number=question_number,
                language=language,
                rng=rng,
                difficulty=difficulty,
                variant_index=variant_index,
            )
        return self._template_question(
            template,
            topic,
            question_number,
            rng,
            difficulty=difficulty,
            language=language,
            variant_index=variant_index,
        )

    def _true_false_question(
        self,
        template: dict[str, Any],
        topic: str,
        question_number: int,
        rng: random.Random,
        language: str,
        difficulty: str,
        variant_index: int,
    ) -> dict[str, Any]:
        use_correct = rng.choice([True, False])
        statement = template["correct"] if use_correct else template["distractors"][0]
        if language == "ar":
            stems = [
                "صح أم خطأ ({difficulty}): {statement}",
                "قيم العبارة ({difficulty}): {statement}",
                "هل تدعم ملاحظات {topic} هذه العبارة؟ {statement}",
                "مراجعة {topic} ({difficulty}): {statement}",
            ]
        else:
            stems = [
                "True or false ({difficulty}): {statement}",
                "Evaluate this {topic} claim ({difficulty}): {statement}",
                "Is this statement supported during {topic} revision? {statement}",
                "Checkpoint claim for {topic} ({difficulty}): {statement}",
            ]
        question_text = stems[variant_index % len(stems)].format(
            topic=topic,
            difficulty=difficulty,
            statement=statement,
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

    def _context_question(
        self,
        *,
        topic: str,
        context_chunk: dict[str, Any],
        question_number: int,
        language: str,
        rng: random.Random,
        difficulty: str,
        variant_index: int,
    ) -> dict[str, Any]:
        answer = self._best_context_sentence(context_chunk.get("text", ""), topic=topic)
        source_label = self._source_label(context_chunk)
        concept = self._context_concept(context_chunk, topic=topic)
        if language == "ar":
            stems = [
                "\u0623\u064a \u0639\u0628\u0627\u0631\u0629 \u062a\u0637\u0627\u0628\u0642 {source} \u0639\u0646 {concept}\u061f",
                "\u0645\u0627 \u0623\u0641\u0636\u0644 \u062a\u0644\u062e\u064a\u0635 \u0644\u0645\u0627 \u064a\u0642\u0648\u0644\u0647 \u0627\u0644\u0645\u0644\u0641 \u0639\u0646 {concept}\u061f",
                "\u0623\u064a \u062e\u064a\u0627\u0631 \u0645\u062f\u0639\u0648\u0645 \u0623\u0643\u062b\u0631 \u0645\u0646 {source}\u061f",
                "\u0628\u062d\u0633\u0628 \u0627\u0644\u0645\u0627\u062f\u0629 \u0627\u0644\u0645\u062d\u062f\u062f\u0629\u060c \u0645\u0627 \u0627\u0644\u0623\u062f\u0642 \u062d\u0648\u0644 {concept}\u061f",
            ]
            question = stems[variant_index % len(stems)].format(source=source_label, concept=concept, topic=topic)
            explanation = f"\u0627\u0644\u0625\u062c\u0627\u0628\u0629 \u0645\u0628\u0646\u064a\u0629 \u0639\u0644\u0649 {source_label}."
        else:
            stems = [
                "Which statement best matches {source} about {concept}?",
                "What is the best summary of the selected file's note on {concept}?",
                "Which option is most directly supported by {source}?",
                "According to the selected material, what should you remember about {concept}?",
            ]
            question = stems[variant_index % len(stems)].format(source=source_label, concept=concept, topic=topic)
            explanation = f"This answer is grounded in {source_label}."

        options, answer_index = self._shuffle_options(
            answer,
            self._context_distractors(
                topic=topic,
                concept=concept,
                answer=answer,
                language=language,
                difficulty=difficulty,
            ),
            rng,
        )
        return {
            "id": f"context-{question_number}",
            "type": "mcq",
            "topic": topic,
            "difficulty": difficulty,
            "question": question,
            "options": options,
            "answer_index": answer_index,
            "explanation": explanation,
            "source": source_label,
        }

    def _short_answer_question(
        self,
        template: dict[str, Any],
        topic: str,
        question_number: int,
        language: str,
        difficulty: str,
        context_chunk: dict[str, Any] | None,
        variant_index: int,
    ) -> dict[str, Any]:
        expected = self._trim(context_chunk.get("text", ""), max_length=180) if context_chunk else template["correct"]
        keywords = self._keywords(expected, topic)
        concept = self._context_concept(context_chunk, topic=topic) if context_chunk else self._template_focus(template)
        if language == "ar":
            prompts = [
                f"إجابة قصيرة ({difficulty}): اشرح {concept} في جملة أو جملتين.",
                f"اكتب ملخصا قصيرا عن {concept} من {topic}.",
                f"ما الفكرة الأهم التي تربط {concept} بالموضوع؟",
                f"أجب باختصار: كيف تستخدم {concept} في المراجعة؟",
            ]
        else:
            prompts = [
                f"Short answer ({difficulty}): Explain {concept} in one or two sentences.",
                f"Briefly summarize how {concept} fits into {topic}.",
                f"What is the key idea connecting {concept} to this material?",
                f"In your own words, how would you use {concept} during revision?",
            ]
        prompt = prompts[variant_index % len(prompts)]
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
        variant_index: int,
    ) -> dict[str, Any]:
        focus = self._template_focus(template)
        if language == "ar":
            pairs = [
                {"left": f"الفكرة الأساسية في {topic}", "right": template["correct"]},
                {"left": f"خطأ شائع في {topic}", "right": template["distractors"][0]},
                {"left": f"حركة تدريب في {topic}", "right": "استخدم مثالا محلولا ثم حل سؤالا جديدا."},
            ]
            stems = [
                "مطابقة ({difficulty}): طابق كل عبارة عن {topic} مع الوصف الأنسب.",
                "طابق مفاتيح {focus} في {topic} مع شرحها.",
                "اختبار مطابقة: ما الدور الأنسب لكل عنصر عن {focus}؟",
                "مراجعة {topic}: اربط المفهوم بالخطأ الشائع والتدريب.",
            ]
        else:
            pairs = [
                {"left": f"{topic} core idea", "right": template["correct"]},
                {"left": f"{topic} common trap", "right": template["distractors"][0]},
                {"left": f"{topic} practice move", "right": "Use a worked example, then solve a new question."},
            ]
            stems = [
                "Matching ({difficulty}): Match each {topic} prompt to the best description.",
                "Match the {focus} cues in {topic} to their best explanations.",
                "Which description belongs with each {topic} revision cue about {focus}?",
                "Pair the concept, common trap, and practice move for {topic}.",
            ]
        question = stems[variant_index % len(stems)].format(
            topic=topic,
            focus=focus,
            difficulty=difficulty,
        )
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
        avoid_questions: list[str],
        previous_normalized: set[str],
        rng: random.Random,
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
        avoid_text = self._format_avoid_questions(avoid_questions)
        prompt = render_prompt(
            "quiz_generation",
            course_name=self._course_name_from_context(context_chunks),
            topic=topic,
            difficulty=difficulty,
            number_of_questions=count,
            question_types=", ".join(question_types),
            context=source_text,
            avoid_questions=avoid_text,
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

        questions = self._normalize_llm_questions(
            payload.get("questions"),
            topic=topic,
            count=count,
            difficulty=difficulty,
            previous_normalized=previous_normalized,
            rng=rng,
        )
        if len(questions) != count:
            return None
        flashcards = self._normalize_llm_flashcards(payload.get("flashcards"))
        if not flashcards:
            flashcards = self._flashcards(topic, context_chunks=context_chunks, language=language)
        return {"questions": questions, "flashcards": flashcards}

    def _normalize_llm_questions(
        self,
        raw_questions: Any,
        *,
        topic: str,
        count: int,
        difficulty: str,
        previous_normalized: set[str],
        rng: random.Random,
    ) -> list[dict[str, Any]]:
        if not isinstance(raw_questions, list):
            return []

        questions = []
        used_normalized = set(previous_normalized)
        for item in raw_questions:
            index = len(questions) + 1
            if index > count:
                break
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
            clean_options = [str(option).strip() for option in options]
            if any(not option for option in clean_options):
                continue
            if len({self._normalize_text(option) for option in clean_options}) != 4:
                continue
            normalized_question = normalize_question_text(question_text)
            if not normalized_question or normalized_question in used_normalized:
                continue
            correct_answer = clean_options[answer_index]
            distractors = [option for option_index, option in enumerate(clean_options) if option_index != answer_index]
            shuffled_options, shuffled_answer_index = self._shuffle_options(correct_answer, distractors, rng)
            questions.append(
                {
                    "id": f"llm-{index}",
                    "type": "mcq",
                    "topic": topic,
                    "difficulty": difficulty,
                    "question": question_text,
                    "options": shuffled_options,
                    "answer_index": shuffled_answer_index,
                    "explanation": str(item.get("explanation") or "").strip(),
                    "source": str(item.get("source") or "llm").strip(),
                }
            )
            used_normalized.add(normalized_question)
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
        *,
        difficulty: str,
        language: str,
        variant_index: int,
    ) -> dict[str, Any]:
        focus = self._template_focus(template)
        distractors = self._template_distractors(
            template,
            topic=topic,
            focus=focus,
            language=language,
            variant_index=variant_index,
        )
        options, answer_index = self._shuffle_options(template["correct"], distractors, rng)
        if language == "ar":
            stems = [
                template["question"],
                "أي اختيار يختبر {focus} في {topic} بشكل أفضل؟",
                "عند مراجعة {topic} بمستوى {difficulty}، ما الخطوة المرتبطة بـ {focus}؟",
                "ما الدليل الأقوى على فهم {focus} ضمن {topic}؟",
            ]
        else:
            stems = [
                template["question"],
                "Which choice best checks {focus} while revising {topic}?",
                "In a {difficulty} review of {topic}, which step supports {focus}?",
                "What is the strongest evidence that you understand {focus} in {topic}?",
            ]
        question_text = stems[variant_index % len(stems)].format(
            topic=topic,
            focus=focus,
            difficulty=difficulty,
        )
        return {
            "id": f"template-{question_number}",
            "type": "mcq",
            "topic": topic,
            "difficulty": difficulty,
            "question": question_text,
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
            best_chunk = self._best_context_sentence(context_chunks[0].get("text", ""), topic=topic)
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
        correct = str(correct or "").strip()
        options = [correct]
        seen = {self._normalize_text(correct)}
        for distractor in distractors:
            clean_distractor = str(distractor or "").strip()
            normalized = self._normalize_text(clean_distractor)
            if not clean_distractor or normalized in seen:
                continue
            options.append(clean_distractor)
            seen.add(normalized)
            if len(options) == 4:
                break
        fallback_index = 1
        while len(options) < 4:
            filler = f"Unsupported option {fallback_index}"
            fallback_index += 1
            if self._normalize_text(filler) in seen:
                continue
            options.append(filler)
            seen.add(self._normalize_text(filler))
        rng.shuffle(options)
        return options, options.index(correct)

    def _clean_topic(self, topic: str) -> str:
        cleaned = re.sub(r"\s+", " ", str(topic or "").strip(" .\u061f?؛:"))
        return cleaned or "Revision"

    def _coerce_count(self, count: Any) -> int:
        try:
            value = int(count or 1)
        except (TypeError, ValueError):
            value = 1
        return min(max(value, 1), self.MAX_QUESTION_COUNT)

    def _normalize_difficulty(self, difficulty: str) -> str:
        normalized = str(difficulty or "medium").strip().lower()
        return normalized if normalized in self.ALLOWED_DIFFICULTIES else "medium"

    def _prepare_context_chunks(self, context_chunks: list[dict[str, Any]]) -> list[dict[str, Any]]:
        prepared = []
        seen: set[tuple[str, str, str]] = set()
        for chunk in context_chunks:
            if not isinstance(chunk, dict):
                continue
            text = self._trim(chunk.get("text", ""), max_length=900)
            if not text:
                continue
            source_name = str(chunk.get("source_name") or chunk.get("source") or "uploaded notes").strip()
            section = str(chunk.get("section") or "section").strip()
            key = (
                source_name.casefold(),
                section.casefold(),
                self._normalize_text(text)[:180],
            )
            if key in seen:
                continue
            seen.add(key)
            prepared.append(
                {
                    **chunk,
                    "source_name": source_name,
                    "section": section,
                    "text": text,
                }
            )
        return prepared[:12]

    def _best_context_sentence(self, text: str, *, topic: str) -> str:
        compact = " ".join(str(text or "").split())
        if not compact:
            return ""
        topic_terms = set(re.findall(r"[\w\u0600-\u06FF]+", topic.lower()))
        sentences = [part.strip() for part in re.split(r"(?<=[.!?\u061f])\s+", compact) if part.strip()]
        if not sentences:
            sentences = [compact]
        ranked = []
        for index, sentence in enumerate(sentences):
            terms = set(re.findall(r"[\w\u0600-\u06FF]+", sentence.lower()))
            ranked.append((len(topic_terms & terms), index, sentence))
        ranked.sort(key=lambda item: (-item[0], item[1]))
        return self._trim(ranked[0][2], max_length=180)

    def _source_label(self, chunk: dict[str, Any]) -> str:
        source = str(chunk.get("source_name") or chunk.get("source") or "uploaded notes").strip()
        section = str(chunk.get("section") or "section").strip()
        return f"{source} ({section})"

    def _context_concept(self, chunk: dict[str, Any] | None, *, topic: str) -> str:
        if not chunk:
            return topic
        sentence = self._best_context_sentence(chunk.get("text", ""), topic=topic)
        topic_tokens = set(re.findall(r"[\w\u0600-\u06FF]+", topic.casefold()))
        keywords = [
            token
            for token in self._keywords(sentence, topic)
            if token.casefold() not in topic_tokens
        ]
        if keywords:
            return " ".join(keywords[:3])
        return self._trim(sentence, max_length=60) or topic

    def _template_focus(self, template: dict[str, Any]) -> str:
        keywords = self._keywords(template.get("correct", ""), "")
        if keywords:
            return " ".join(keywords[:3])
        return self._trim(template.get("correct", ""), max_length=50) or "the core idea"

    def _template_distractors(
        self,
        template: dict[str, Any],
        *,
        topic: str,
        focus: str,
        language: str,
        variant_index: int,
    ) -> list[str]:
        base = [str(item) for item in template.get("distractors", []) if str(item or "").strip()]
        if base:
            rotation = variant_index % len(base)
            base = base[rotation:] + base[:rotation]
        if language == "ar":
            specific = [
                f"التعامل مع {focus} كعنوان فقط دون مثال من {topic}.",
                f"اختيار إجابة تبدو مألوفة دون ربطها بالملاحظات.",
                f"تجاهل التطبيق العملي لـ {focus} والتركيز على الشكل فقط.",
            ]
        else:
            specific = [
                f"Treat {focus} as only a label, without an example from {topic}.",
                "Choose an answer because it sounds familiar, not because the notes support it.",
                f"Ignore the practical use of {focus} and focus only on note formatting.",
            ]
        return [*specific[variant_index % len(specific) :], *specific[: variant_index % len(specific)], *base]

    def _format_avoid_questions(self, avoid_questions: list[str]) -> str:
        cleaned = []
        for question in avoid_questions:
            text = self._trim(question, max_length=180)
            if text and text not in cleaned:
                cleaned.append(text)
            if len(cleaned) == 20:
                break
        if not cleaned:
            return "None."
        return "\n".join(f"- {question}" for question in cleaned)

    def _context_distractors(
        self,
        *,
        topic: str,
        concept: str,
        answer: str,
        language: str,
        difficulty: str,
    ) -> list[str]:
        del answer
        if language == "ar":
            if difficulty == "hard":
                return [
                    f"{concept} في {topic} مجرد تسمية تحفظ دون أمثلة أو تطبيق.",
                    f"الملف يوضح أن {concept} غير مرتبط بالتحليل أو حل الأسئلة.",
                    f"أفضل تعامل مع {concept} هو تجاهل الشرح والانتقال لموضوع آخر.",
                ]
            return [
                f"لا توجد أي فكرة في الملف مرتبطة بـ {concept}.",
                f"{concept} يعني حفظ عنوان {topic} فقط.",
                f"لا تحتاج إلى تطبيق أو اختبار فهم {concept}.",
            ]
        if difficulty == "hard":
            return [
                f"{concept} in {topic} is only a label to memorize, not an idea to apply.",
                f"The file shows {concept} has no link to analysis, examples, or practice.",
                f"The best response to {concept} is to ignore the explanation and switch topics.",
            ]
        return [
            f"The selected file has no idea connected to {concept}.",
            f"{concept} only means memorizing the title of {topic}.",
            f"There is no need to apply or test {concept} after reading.",
        ]

    def _trim(self, text: str, *, max_length: int) -> str:
        compact = " ".join(str(text or "").split())
        if len(compact) <= max_length:
            return compact
        return f"{compact[:max_length].rsplit(' ', 1)[0].rstrip()}..."

    def _normalize_question_types(self, question_types: list[str] | None) -> list[str]:
        normalized = [str(item).strip().lower() for item in question_types or ["mcq"]]
        selected = [item for item in normalized if item in self.ALLOWED_QUESTION_TYPES]
        return selected or ["mcq"]

    def _normalize_text(self, text: str) -> str:
        return re.sub(r"\s+", " ", str(text or "").strip().casefold())

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
