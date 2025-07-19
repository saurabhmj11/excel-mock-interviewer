import json
import os
import datetime
from typing import List, Dict, Any, Optional

# --- Basic Data Models ---
# In a larger project, these would likely be in a separate 'models.py' file.
class Question:
    def __init__(self, id: str, text: str, difficulty: str, topic: str, ideal_answer: str):
        self.id = id
        self.text = text
        self.difficulty = difficulty
        self.topic = topic
        self.ideal_answer = ideal_answer # Used for RAG or as reference

class UserAnswer:
    def __init__(self, question_id: str, user_response: str, timestamp: str):
        self.question_id = question_id
        self.user_response = user_response
        self.timestamp = timestamp

class GradedAnswer:
    def __init__(self, question_id: str, user_response: str, correctness: str, justification: str, tips_for_improvement: str, score: float):
        self.question_id = question_id
        self.user_response = user_response # Store user's original response for context
        self.correctness = correctness
        self.justification = justification
        self.tips_for_improvement = tips_for_improvement
        self.score = score # e.g., 1.0 for Correct, 0.5 for Partial, 0.0 for Incorrect

class InterviewState:
    def __init__(self, session_id: str):
        self.session_id: str = session_id
        self.status: str = "active" # "active", "completed", "aborted"
        self.questions_asked: List[Question] = [] # Questions actually presented to the user
        self.current_question_index: int = 0
        self.user_answers: List[UserAnswer] = []
        self.graded_answers: List[GradedAnswer] = []
        self.overall_score: float = 0.0
        self.start_time: str = ""
        self.end_time: Optional[str] = None

# --- InterviewAgent Class ---
class InterviewAgent:
    def __init__(self, questions_file: str = "questions.json"):
        self.questions_file = questions_file
        self.questions: List[Question] = self._load_questions()
        self.interview_state: InterviewState = InterviewState(session_id=self._generate_session_id())

    def _generate_session_id(self) -> str:
        """Generates a unique session ID based on timestamp."""
        return datetime.datetime.now().strftime("%Y%m%d%H%M%S")

    def _load_questions(self) -> List[Question]:
        """Loads and sorts questions from the JSON file."""
        if not os.path.exists(self.questions_file):
            raise FileNotFoundError(f"Questions file not found: {self.questions_file}")
        
        with open(self.questions_file, 'r', encoding='utf-8') as f:
            data = json.load(f)
        
        # Sort questions by difficulty (easy, medium, hard)
        # Unknown difficulties will be treated as medium.
        difficulty_order = {"easy": 1, "medium": 2, "hard": 3}
        sorted_data = sorted(data, key=lambda x: difficulty_order.get(x.get("difficulty", "medium"), 2))
        
        questions = []
        for q_data in sorted_data:
            questions.append(Question(
                id=q_data['id'],
                text=q_data['text'],
                difficulty=q_data.get('difficulty', 'medium'),
                topic=q_data.get('topic', 'General'),
                ideal_answer=q_data.get('ideal_answer', '')
            ))
        return questions

    def start_interview(self) -> str:
        """Initializes the interview state and provides an introduction message."""
        self.interview_state.status = "active"
        self.interview_state.start_time = self._generate_session_id()
        
        intro_message = (
            "Hello! Welcome to the AI-Powered Excel Mock Interviewer.\n"
            "I'm here to test your Excel knowledge. I will ask you a series of questions.\n"
            "Please provide your answers as clearly and completely as possible.\n"
            "You can type 'quit' at any time to end the interview.\n"
            "Let's begin!"
        )
        print(intro_message)
        return intro_message

    def get_current_question(self) -> Optional[Question]:
        """Returns the current question to be asked, or None if all questions are asked."""
        if self.interview_state.current_question_index < len(self.questions):
            question = self.questions[self.interview_state.current_question_index]
            # Record that this question has been asked
            if question not in self.interview_state.questions_asked:
                self.interview_state.questions_asked.append(question)
            return question
        return None

    def advance_question(self):
        """Moves the interview to the next question."""
        self.interview_state.current_question_index += 1

    def record_user_answer(self, user_response: str) -> UserAnswer:
        """Records the user's answer for the current question."""
        current_question = self.get_current_question()
        if not current_question:
            raise ValueError("No current question to answer.")

        user_answer = UserAnswer(
            question_id=current_question.id,
            user_response=user_response,
            timestamp=self._generate_session_id()
        )
        self.interview_state.user_answers.append(user_answer)
        return user_answer

    def record_graded_answer(self, graded_answer: GradedAnswer):
        """Records the graded answer and updates the overall score based on correctness."""
        self.interview_state.graded_answers.append(graded_answer)
        
        # Update overall score based on the graded correctness
        if graded_answer.correctness == "Correct":
            self.interview_state.overall_score += 1.0
        elif graded_answer.correctness == "Partially Correct":
            self.interview_state.overall_score += 0.5
        # No score added for "Incorrect" or "Error"

    def end_interview(self) -> str:
        """Marks the interview as completed and provides a closing message."""
        self.interview_state.status = "completed"
        self.interview_state.end_time = self._generate_session_id()
        
        num_questions_asked = len(self.interview_state.questions_asked)
        closing_message = (
            "\nThank you for completing the Excel mock interview!\n"
            "I've recorded your answers. A detailed feedback report will be generated shortly.\n"
            f"You answered {len(self.interview_state.user_answers)} out of {num_questions_asked} questions."
        )
        print(closing_message)
        return closing_message

    def get_interview_summary(self) -> Dict[str, Any]:
        """
        Returns a comprehensive summary of the current interview state,
        including questions asked, user answers, graded answers, and overall score.
        """
        return {
            "session_id": self.interview_state.session_id,
            "questions_asked": [q.__dict__ for q in self.interview_state.questions_asked],
            "user_answers": [ua.__dict__ for ua in self.interview_state.user_answers],
            "graded_answers": [ga.__dict__ for ga in self.interview_state.graded_answers],
            "overall_score": self.interview_state.overall_score,
            "total_possible_score": len(self.interview_state.questions_asked), # Max 1 point per question
            "status": self.interview_state.status,
            "start_time": self.interview_state.start_time,
            "end_time": self.interview_state.end_time
        }
