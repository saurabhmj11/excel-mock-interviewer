import streamlit as st
import os
import json
import datetime
from interview_agent import InterviewAgent, Question, UserAnswer, GradedAnswer, InterviewState
from grader import Grader
from feedback_generator import FeedbackGenerator
# No direct import of RAGManager here, as it's managed by Grader

# --- Initialize components and state ---
if 'agent' not in st.session_state:
    try:
        st.session_state.agent = InterviewAgent()
        # <--- MODIFIED: Pass agent.questions to Grader
        st.session_state.grader = Grader(questions=st.session_state.agent.questions) 
        st.session_state.feedback_gen = FeedbackGenerator()
        
        st.session_state.interview_started = False
        st.session_state.current_question_obj = None
        st.session_state.interview_finished = False
    except ValueError as e:
        st.error(f"Configuration Error: {e}. Please ensure your OPENAI_API_KEY environment variable is set.")
        st.stop()
    except FileNotFoundError as e:
        st.error(f"Error: {e}. Please ensure 'questions.json' is in the root directory.")
        st.stop()
    except Exception as e:
        st.error(f"An unexpected error occurred during initialization: {e}")
        st.stop()
    st.info("System initialized. Click 'Start Interview' to begin.") # Added initialization message

# --- Functions for interview flow ---
def start_interview():
    st.session_state.agent.start_interview()
    st.session_state.current_question_obj = st.session_state.agent.get_current_question()
    st.session_state.interview_started = True
    st.session_state.interview_finished = False # Reset for new interview
    st.session_state.user_answer_input = "" # Clear input box
    if 'last_evaluation' in st.session_state:
        del st.session_state.last_evaluation # Clear previous evaluation feedback

def submit_answer():
    user_response = st.session_state.user_answer_input
    if user_response.lower().strip() == 'quit':
        st.session_state.agent.interview_state.status = "aborted"
        st.session_state.interview_finished = True
        return

    if st.session_state.current_question_obj and user_response:
        with st.spinner("Evaluating your answer..."):
            st.session_state.agent.record_user_answer(user_response)
            
            # Grade the answer
            graded_answer = st.session_state.grader.grade_answer(st.session_state.current_question_obj, user_response)
            
            st.session_state.agent.record_graded_answer(graded_answer)
            
            st.session_state.last_evaluation = {
                "correctness": graded_answer.correctness,
                "justification": graded_answer.justification,
                "tips": graded_answer.tips_for_improvement
            }
        
        # Advance to next question
        st.session_state.agent.advance_question()
        next_question = st.session_state.agent.get_current_question()
        
        if next_question:
            st.session_state.current_question_obj = next_question
            st.session_state.user_answer_input = "" # Clear input box for next question
        else:
            st.session_state.interview_finished = True
            st.session_state.agent.end_interview()
        
        st.rerun() # Always rerun after submit to update UI

# --- Streamlit UI Layout ---
st.set_page_config(page_title="AI Excel Interviewer", layout="centered")

st.title("🧠 AI-Powered Excel Mock Interviewer")
st.markdown("Simulate an Excel technical interview and get detailed feedback on your skills.")

if not st.session_state.interview_started:
    if st.button("Start Interview", key="start_button"):
        start_interview()
        st.rerun() # Rerun to update UI with first question

if st.session_state.interview_started:
    if not st.session_state.interview_finished:
        # Check if current_question_obj is valid before displaying
        if st.session_state.current_question_obj:
            st.subheader(f"Question {st.session_state.agent.interview_state.current_question_index + 1} of {len(st.session_state.agent.questions)}")
            
            current_q = st.session_state.current_question_obj
            st.markdown(f"**Topic:** _{current_q.topic}_")
            st.markdown(f"**Difficulty:** _{current_q.difficulty.capitalize()}_")
            st.write(f"**Question:** {current_q.text}")
            
            # Display last evaluation feedback
            if 'last_evaluation' in st.session_state and st.session_state.last_evaluation:
                with st.expander(f"Last Answer Evaluation: **{st.session_state.last_evaluation['correctness']}**"):
                    st.write(f"**Correctness:** {st.session_state.last_evaluation['correctness']}")
                    st.write(f"**Justification:** {st.session_state.last_evaluation['justification']}")
                    st.write(f"**Tips for Improvement:** {st.session_state.last_evaluation['tips']}")

            # User input area
            st.text_area(
                "Your Answer:",
                value=st.session_state.get('user_answer_input', ''), # Use value from session_state for persistence
                key="user_answer_input",
                height=150,
                help="Type your Excel answer or explanation here. Type 'quit' to end the interview early."
            )
            
            # Ensure the button is outside the expander if using one
            if st.button("Submit Answer", key="submit_answer_button"):
                submit_answer() # This handles the rerun
        else:
            st.warning("No more questions available to display. Interview should be finishing.")
            # This block helps catch unexpected states; if here, interview_finished should be true.
            st.session_state.interview_finished = True
            st.session_state.agent.end_interview()
            st.rerun()

    else: # Interview is finished
        st.success("Interview completed! Generating your final feedback report..." if st.session_state.agent.interview_state.status != "aborted" else "Interview aborted.")
        
        if st.session_state.agent.interview_state.status != "aborted":
            with st.spinner("Compiling detailed feedback report..."):
                final_report = st.session_state.feedback_gen.generate_feedback_report(st.session_state.agent.interview_state)
            
            st.markdown("---")
            st.markdown("## 📋 Final Feedback Report")
            st.markdown(final_report)
            st.markdown("---")

            # Save report and transcript
            session_id = st.session_state.agent.interview_state.session_id
            os.makedirs("sample_transcripts", exist_ok=True)
            
            report_filename = f"report_{session_id}.md"
            with open(os.path.join("sample_transcripts", report_filename), "w", encoding="utf-8") as f:
                f.write(final_report)
            
            transcript_filename = f"transcript_{session_id}.json"
            with open(os.path.join("sample_transcripts", transcript_filename), "w", encoding="utf-8") as f:
                # Convert the full state to a serializable dictionary
                serializable_summary = st.session_state.agent.get_interview_summary()
                json.dump(serializable_summary, f, indent=2)
                
            st.info(f"Detailed feedback report saved as: `sample_transcripts/{report_filename}`")
            st.info(f"Full interview transcript saved as: `sample_transcripts/{transcript_filename}`")

        # Option to start a new interview
        if st.button("Start New Interview", key="new_interview_button"):
            # Clear all session state variables to restart clean
            for key in list(st.session_state.keys()): # Use list() to avoid RuntimeError during iteration
                del st.session_state[key]
            st.rerun() # Rerun to refresh the app