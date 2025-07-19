import os
import json
from interview_agent import InterviewAgent, GradedAnswer 
from grader import Grader 
from feedback_generator import FeedbackGenerator 

def run_cli_interview():
    print("🚀 Initializing AI-Powered Excel Mock Interviewer...")
    try:
        agent = InterviewAgent()
        # Initialize Grader with ALL questions for RAGManager to build its KB
        grader = Grader(questions=agent.questions) # <--- MODIFIED: Pass agent.questions
        feedback_gen = FeedbackGenerator() 
    except FileNotFoundError as e:
        print(f"Error: {e}")
        print("Please ensure 'questions.json' is in the same directory as 'main.py'.")
        return
    except ValueError as e: 
        print(f"Configuration Error: {e}")
        print("Please set your OPENAI_API_KEY environment variable.")
        return
    except Exception as e:
        print(f"An unexpected error occurred during initialization: {e}")
        return

    agent.start_interview()

    while True:
        current_question = agent.get_current_question()
        if not current_question:
            break

        print(f"\n--- Question {agent.interview_state.current_question_index + 1} of {len(agent.questions)} ({current_question.difficulty.upper()}) ---")
        print(f"Topic: {current_question.topic}")
        print(f"Q: {current_question.text}")
        
        user_response = input("Your Answer (type 'quit' to end): \n> ")

        if user_response.lower().strip() == 'quit':
            agent.interview_state.status = "aborted"
            print("\nInterview aborted by user.")
            break

        agent.record_user_answer(user_response)
        print("Evaluating your answer... Please wait.")
        
        graded_answer = grader.grade_answer(current_question, user_response)
        agent.record_graded_answer(graded_answer)
        
        print(f"\n--- Evaluation for Question {current_question.id} ---")
        print(f"Correctness: {graded_answer.correctness}")
        print(f"\nJustification: {graded_answer.justification}")
        print(f"\nTips for Improvement: {graded_answer.tips_for_improvement}")
        print("--------------------------------------------------")

        agent.advance_question()

    agent.end_interview()
    
    final_report = feedback_gen.generate_feedback_report(agent.interview_state)
    print("\n" + "#" * 60)
    print("                 FINAL FEEDBACK REPORT")
    print("#" * 60)
    print(final_report)
    print("#" * 60)
    print(f"\nInterview session complete. Report saved to console (and will eventually be saved to a file if desired).")
    
    session_id = agent.interview_state.session_id
    report_filename = f"report_{session_id}.md"
    os.makedirs("sample_transcripts", exist_ok=True) 
    with open(os.path.join("sample_transcripts", report_filename), "w", encoding="utf-8") as f:
        f.write(final_report)
    print(f"Detailed feedback report saved as: sample_transcripts/{report_filename}")

    transcript_filename = f"transcript_{session_id}.json"
    with open(os.path.join("sample_transcripts", transcript_filename), "w", encoding="utf-8") as f:
        json.dump(agent.get_interview_summary(), f, indent=2)
    print(f"Full interview transcript saved as: sample_transcripts/{transcript_filename}")