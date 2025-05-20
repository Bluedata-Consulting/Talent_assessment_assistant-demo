import streamlit as st
from src.utils import HRBackend
import os 
import pandas as pd
import numpy as np

st.set_page_config(page_title="Talent Assessment Assistant", layout="wide")

# Title and Description
st.title("Talent Assessment Assistant")
st.write("Welcome! Our HR team is here to assist you with your interview process.")

# Initialize backend
if 'backend' not in st.session_state:
    st.session_state.backend = HRBackend()

backend = st.session_state.backend

# Main chat logic
def main():
    # Chat display area
    chat_container = st.container()
    with chat_container:
        for chat in backend.chat_history:
            if chat["align"] == "left":
                st.markdown(
                    f"""
                    <div style='display: flex; justify-content: flex-start; margin: 10px 0;'>
                        <div style='background-color: #c8ffc9; color: #000000; padding: 10px; border-radius: 10px; max-width: 60%;'>
                            {chat['message']}
                        </div>
                    </div>
                    """,
                    unsafe_allow_html=True
                )
            else:
                st.markdown(
                    f"""
                    <div style='display: flex; justify-content: flex-end; margin: 10px 0;'>
                        <div style='background-color: #0056b3; color: #ffffff; padding: 10px; border-radius: 10px; max-width: 60%;'>
                            {chat['message']}
                        </div>
                    </div>
                    """,
                    unsafe_allow_html=True
                )

    # Chat logic
    if backend.stage == 'initial':
        # Display HR's initial message only once
        
        col1, col2, col3 = st.columns([1, 3, 1])
        user_input = col3.text_input("Your response:", key="initial_input", placeholder="Type your message here...")
        if user_input:  # Check if user has entered something
            backend.add_to_chat("User", user_input, "right")
            backend.add_to_chat("HR", "Hello!", "left")
            backend.add_to_chat("HR", "Please select the role you're applying for:", "left")
            backend.stage = 'role_selection'
            st.rerun()

    elif backend.stage == 'role_selection':
        col1, col2, col3 = st.columns([1, 3, 1])
        role = col1.selectbox("Choose a role:", ["Software Engineer", "Data Scientist", "Product Manager", "Other"], key="role_select")
        experience = col1.selectbox("Select your experience level:", ["Entry-Level", "Mid-Level", "Senior-Level"], key="exp_select")
        
        if col1.button("Confirm Selection"):
            backend.role = role
            backend.experience = experience
            backend.add_to_chat("User", f"Role: {role}, Experience: {experience}", "right")
            backend.add_to_chat("HR", f"Great! You're applying for {role} at {experience} level.", "left")
            backend.add_to_chat("HR", "Please upload your resume:", "left")
            backend.stage = 'resume_upload'
            st.rerun()

    elif backend.stage == 'resume_upload':
        col1, col2, col3 = st.columns([1, 2, 1])
        # Resume upload
        resume = col1.file_uploader("Upload your resume (PDF)", type=["pdf"], key="resume_uploader")
        
        if resume is not None:
            backend.resume = resume
            # full_path = os.path.join("uploads", backend.resume.name)
            # backend.full_path = full_path
            backend.save_resume(resume)  # Save the resume silently
            resume_data = backend.resume_reader()
            
            backend.add_to_chat("User", f"Resume uploaded: {resume.name}", "right")
            backend.add_to_chat("HR", "Thank you for uploading your resume. Now let's proceed with some questions.", "left")
            
            # Get the first question and display it
            current_question = backend.get_next_question()
            backend.add_to_chat("HR", current_question, "left")
            
            # Move to the questions stage
            backend.stage = 'answering'
            st.rerun()

    elif backend.stage == 'answering':
        col1, col2, col3 = st.columns([1, 3, 1])
        
        # Get current question (already displayed in chat)
        current_question = backend.questions[backend.current_question_index]
        
        # Provide text input for user's answer
        user_answer = col3.text_area("Your answer:", key=f"answer_{backend.current_question_index}", 
                                     placeholder="Type your answer here...")
        
        if col3.button("Submit Answer", key=f"submit_{backend.current_question_index}"):
            if user_answer:
                # Save user's answer to chat history
                backend.add_to_chat("User", user_answer, "right")
                
                # Save response and increment question index
                backend.save_response(current_question, user_answer)
                
                # Check if there are more questions
                if backend.current_question_index < len(backend.questions):
                    # Get and display next question
                    next_question = backend.get_next_question()
                    if next_question:
                        backend.add_to_chat("HR", next_question, "left")
                        st.rerun()
                else:
                    # All questions answered, move to completed stage
                    backend.add_to_chat("HR", "Thank you for your responses! We'll review your application and get back to you soon.", "left")
                    backend.stage = 'completed'
                    st.rerun()
            else:
                st.error("Please provide an answer before submitting.")
    
    elif backend.stage == 'completed':
        col1, col2, col3 = st.columns([1, 3, 1])
        questions_list = backend.responses.keys()
        score_dict = backend.scores
    
        df = pd.DataFrame(
            {
                "Questions": questions_list,
                "Score": score_dict
            }
        ).reset_index(drop=True)
    
        with col2:
            st.markdown("<div style='margin-top: 30px;'></div>", unsafe_allow_html=True)
            st.table(df)
    
        try:
            col2.write(f"TotalScore = {np.mean(list(score_dict))}%")
        except TypeError as e:
            print(e)
            col2.write("TotalScore = 0%")

# Custom CSS for better styling
st.markdown("""
<style>
    .stButton>button {
        background-color: #4CAF50;
        color: white;
        border-radius: 5px;
        padding: 10px 20px;
    }
    .stButton>button:hover {
        background-color: #45a049;
    }
    .stFileUploader {
        border: 2px dashed #cccccc;
        border-radius: 5px;
        padding: 10px;
    }
    .stTextArea textarea {
        min-height: 100px;
    }
</style>
""", unsafe_allow_html=True)

if __name__ == "__main__":
    main()