import os
import json
from typing import Dict, Any, List
from openai import OpenAI
from interview_agent import InterviewState, Question, GradedAnswer # Import necessary data models

class FeedbackGenerator:
    def __init__(self):
        self.client = OpenAI()
        if not os.getenv("OPENAI_API_KEY"):
            raise ValueError("OPENAI_API_KEY environment variable not set. Please set it to proceed.")

    def generate_feedback_report(self, interview_state: InterviewState) -> str:
        """
        Generates a detailed feedback report based on the interview state using an LLM.
        """
        questions_data = []
        for q_idx, question in enumerate(interview_state.questions_asked):
            graded_answer = next((ga for ga in interview_state.graded_answers if ga.question_id == question.id), None)
            
            # Prepare data for detailed LLM prompt
            question_entry = {
                "question_number": q_idx + 1,
                "question_text": question.text,
                "difficulty": question.difficulty,
                "topic": question.topic,
                "user_response": graded_answer.user_response if graded_answer else "N/A (No answer recorded)",
                "evaluation": {
                    "correctness": graded_answer.correctness if graded_answer else "N/A",
                    "justification": graded_answer.justification if graded_answer else "N/A",
                    "tips_for_improvement": graded_answer.tips_for_improvement if graded_answer else "N/A"
                }
            }
            questions_data.append(question_entry)

        # Calculate score and total questions
        total_questions = len(questions_data)
        score_breakdown = interview_state.overall_score
        
        # Craft the prompt for the LLM
        prompt = f"""
You are an AI-powered Excel interview feedback generator. Your task is to analyze the candidate's performance in a mock Excel interview and provide a comprehensive, constructive feedback report.

Here is the data from the interview session:

Interview Session ID: {interview_state.session_id}
Total Questions Asked: {total_questions}
Candidate's Score (Correct=1.0, Partially Correct=0.5, Incorrect=0.0): {score_breakdown} out of {total_questions}.

---
Individual Question Performance:
{json.dumps(questions_data, indent=2)}
---

Generate a detailed feedback report in Markdown format with the following sections:

## 📊 Overall Performance Summary
- Provide a high-level summary of the candidate's performance, including their score and general impressions.
- Mention the range of topics covered and overall proficiency.

## 💪 Strengths
- Identify areas where the candidate demonstrated strong knowledge and understanding.
- Reference specific questions or Excel concepts where they performed well.

## ⚠️ Areas for Improvement
- Pinpoint specific Excel topics or functionalities where the candidate struggled or provided incomplete/incorrect answers.
- Be concrete and refer to the individual question evaluations (e.g., "The candidate struggled with Q3 on PivotTables...").

## 📚 Suggested Resources for Improvement
- Recommend specific types of resources (e.g., "Microsoft Excel Documentation on Data Validation", "Online Courses on Advanced Formulas", "YouTube tutorials on Power Query").
- Suggest general study strategies (e.g., "Practice building models from scratch", "Work through real-world case studies").
- Focus on practical, actionable advice.

## Next Steps
- Offer encouraging final remarks and advise on how to continue improving their Excel skills.

Ensure the tone is professional, supportive, and provides clear pathways for skill enhancement.
"""
        try:
            print("Generating detailed feedback report... This might take a moment.")
            chat_completion = self.client.chat.completions.create(
                model="gpt-4o-mini", # Using gpt-4o-mini for balance
                messages=[
                    {"role": "system", "content": "You are an expert Excel interview feedback generator. You provide comprehensive, constructive reports in clear Markdown format."},
                    {"role": "user", "content": prompt}
                ],
                temperature=0.7, # Higher temperature for more creative/varied advice
                max_tokens=1000 # Limit token output for report length
            )
            
            report = chat_completion.choices[0].message.content
            return report

        except Exception as e:
            print(f"An error occurred during feedback report generation: {e}")
            return (
                "\n## Error Generating Feedback Report\n"
                f"Unfortunately, an error occurred while trying to generate your detailed feedback report: {e}\n"
                "Please check your API key, network connection, or try again later."
            )