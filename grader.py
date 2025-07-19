import os
import json
from typing import Dict, Any, List
from openai import OpenAI
from interview_agent import Question, UserAnswer, GradedAnswer 
from rag_manager import RAGManager # <--- NEW: Import RAGManager

class Grader:
    def __init__(self, questions: List[Question]): # <--- MODIFIED: Accepts all questions
        self.client = OpenAI() 

        if not os.getenv("OPENAI_API_KEY"):
            raise ValueError("OPENAI_API_KEY environment variable not set. Please set it to proceed.")
        
        # <--- NEW: Initialize RAGManager
        try:
            self.rag_manager = RAGManager(questions)
        except Exception as e:
            print(f"Error initializing RAGManager: {e}")
            self.rag_manager = None # If RAG fails, proceed without it, but warn
            print("Proceeding without RAG integration for grading, evaluations may be less precise.")


    def grade_answer(self, question: Question, user_answer_text: str) -> GradedAnswer:
        """
        Evaluates a user's answer to a given question using an LLM.
        The LLM is prompted to return a structured JSON output.
        """
        # <--- NEW: Retrieve context from RAG
        retrieved_context = ""
        if self.rag_manager:
            # Use the question text as the query for context retrieval
            context_results = self.rag_manager.retrieve_context(question.text)
            if context_results:
                # We expect the most relevant context to be the ideal answer for the current question
                # or a very similar concept.
                relevant_docs = [item['document'] for item in context_results]
                retrieved_context = "\n\n--- Relevant Excel Knowledge ---\n" + "\n".join(relevant_docs) + "\n------------------------------------"
                print(f"[RAG] Retrieved context for '{question.id}'.")
            else:
                print(f"[RAG] No context retrieved for '{question.id}'.")


        prompt = f"""
You are an Excel interview evaluator with deep expertise in all functionalities of Microsoft Excel. 
Your task is to objectively evaluate a candidate's answer to an Excel technical question.

---
Question: {question.text}
Candidate's Answer: {user_answer_text}
---

{retrieved_context}  # <--- NEW: Inject retrieved context into the prompt

Carefully consider the provided relevant Excel knowledge (if any) when evaluating the candidate's answer.
Your evaluation should be precise, fair, and actionable. Based on your Excel knowledge and the provided context, 
analyze the candidate's answer for correctness, completeness, and clarity.

Provide your evaluation in a structured JSON format with the following keys:
- "correctness": (Correct / Partially Correct / Incorrect) - Choose exactly one of these three options based on the answer's accuracy.
- "justification": A concise explanation of why the answer received that correctness rating. Highlight strong points, inaccuracies, or missing key details. Refer to specific Excel concepts or functions mentioned in the context or your general knowledge.
- "tips_for_improvement": Provide specific, actionable advice for the candidate to improve their understanding or future answers. Include actual Excel syntax, best practices, or conceptual clarification if applicable. Suggest what they might have missed or could have explained better.

Ensure the "correctness" field strictly adheres to one of the three specified exact strings: "Correct", "Partially Correct", or "Incorrect".
"""
        try:
            chat_completion = self.client.chat.completions.create(
                model="gpt-4o-mini", 
                messages=[
                    {"role": "system", "content": "You are a helpful and expert AI assistant that evaluates Excel interview answers. You always output valid JSON according to the specified schema."},
                    {"role": "user", "content": prompt}
                ],
                response_format={"type": "json_object"},
                temperature=0.2 
            )
            
            evaluation_raw = chat_completion.choices[0].message.content
            evaluation_dict = json.loads(evaluation_raw)

            correctness = evaluation_dict.get("correctness", "Incorrect")
            if correctness not in ["Correct", "Partially Correct", "Incorrect"]:
                print(f"Warning: LLM returned unexpected correctness: '{correctness}'. Falling back to 'Incorrect'.")
                correctness = "Incorrect" 

            justification = evaluation_dict.get("justification", "No justification provided by AI.")
            tips_for_improvement = evaluation_dict.get("tips_for_improvement", "No specific tips provided by AI.")

            score = 0.0
            if correctness == "Correct":
                score = 1.0
            elif correctness == "Partially Correct":
                score = 0.5
            
            return GradedAnswer(
                question_id=question.id,
                user_response=user_answer_text,
                correctness=correctness,
                justification=justification,
                tips_for_improvement=tips_for_improvement,
                score=score
            )

        except json.JSONDecodeError as e:
            print(f"Error: LLM did not return valid JSON. Raw response: {evaluation_raw}. Error: {e}")
            return GradedAnswer(
                question_id=question.id,
                user_response=user_answer_text,
                correctness="Error", 
                justification=f"AI response was not valid JSON: {e}",
                tips_for_improvement="Ensure the LLM generates valid JSON. Check prompt and model settings.",
                score=0.0
            )
        except Exception as e:
            print(f"An unexpected error occurred during LLM evaluation: {e}")
            return GradedAnswer(
                question_id=question.id,
                user_response=user_answer_text,
                correctness="Error", 
                justification=f"An unexpected error occurred: {e}",
                tips_for_improvement="Please check your OpenAI API key and network connection. Also verify ChromaDB setup.",
                score=0.0
            )