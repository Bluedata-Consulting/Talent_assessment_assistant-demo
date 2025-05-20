import os
from langchain_community.document_loaders import PyPDFLoader
from langchain_core.output_parsers import StrOutputParser
from pydantic import Field, BaseModel
from langchain_core.output_parsers import JsonOutputParser
from langchain_openai import ChatOpenAI
from langchain_core.prompts import PromptTemplate
from dotenv import load_dotenv
import sqlite3
import json
load_dotenv()

class extract_data(BaseModel):
    name: str = Field(description="write the name of the person")
    questions: list = Field(description="make 5 questions from the given description in short")

class HRBackend:
    def __init__(self):
        self.chat_history = []
        self.stage = 'initial'
        self.user_name = ''
        self.role = ''
        self.experience = ''
        self.resume = None
        self.full_path = None
        self.questions = []
        self.current_question_index = 0
        self.responses = {}  # Dictionary to store questions and answers
        self.scores = []
        self.resume_data = ""
        self.api_key = os.getenv("OPENAI_API_KEY")

    def add_to_chat(self, sender, message, align="left"):
        self.chat_history.append({"sender": sender, "message": message, "align": align})

    def save_resume(self, resume):
        print('==============================',resume,'==========================')
        if resume:
            # Create a directory for uploads if it doesn't exist
            os.makedirs("uploads", exist_ok=True)
            file_path = os.path.join("uploads", f"{resume.name}")
            
            with open(file_path, "wb") as f:
                f.write(resume.getbuffer())
            
            self.resume_data = self.resume_reader()
            
            return f"Resume saved as {file_path}"
        return "No resume to save."

    def reset(self):
        """Reset all state variables to start a new application"""
        self.stage = 'initial'
        self.role = ''
        self.experience = ''
        self.resume = None
        self.current_question_index = 0
        self.responses = {}
        self.chat_history = []

    def get_next_question(self):
        """Get the current question and return it"""
        query_data = self.get_questions()
        self.questions = query_data['questions']
        if self.current_question_index < len(self.questions):
            question = self.questions[self.current_question_index]
            return question
        return None

    def save_response(self, question, answer):
        """Save the user's response and increment the question index"""
        self.responses[question] = answer
        self.current_question_index += 1
        if len(self.responses) == 5:
            self.create_db()
            # add in db
            user_data = self.get_user_data()
            candidate_name = user_data["name"]
            candidate_questions = user_data['questions']
            scores_data = self.get_score(self.responses)
            self.scores = list(scores_data.values())
            self.insert_record(candidate_name, candidate_questions, answer, self.scores)
            

        
    def get_all_responses(self):
        """Return all questions and answers for review"""
        return self.responses
    
    def resume_reader(self):
        file_path = os.path.join("uploads", f"{self.resume.name}")
        loader = PyPDFLoader(file_path)
        resume_contnet = ""
        for page in loader.load():
            resume_contnet += page.page_content
        return resume_contnet
    

 
    def get_questions(self):
        prompt = """
            Based on the detail of the candidate Generate 5 questions which i can ask to candidate to test his skills .Return the output as a JSON object with the fields 'questions' (list of five strings) and user name with field 'name'.
    
            Job Role: {role}
            Experience Level: {resume}
            Skills: {experience}
    
            Output format:
            {format_instructions}
        """
        parser = JsonOutputParser(pydantic_object=extract_data)
        prompt = PromptTemplate(
            template=prompt,
            input_variables=["role", "experience", "resume"],
            partial_variables={"format_instructions": parser.get_format_instructions()},
        )
    
        llm = ChatOpenAI(model_name="gpt-4o", api_key=self.api_key, temperature=0)
    
        chain = prompt | llm | parser
    
        response = chain.invoke({"role":self.role,"resume":self.resume,"experience":self.experience})  
        return response
    
    def get_user_data(self):
        user_data = self.get_questions()
        return user_data

    def create_db(self):
        # Connect to candidate.db
        conn = sqlite3.connect('candidate.db')
        cursor = conn.cursor()

        # Create the table
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS candidates (
                user_id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_name TEXT NOT NULL,
                questions TEXT,  
                answers TEXT,  
                scores TEXT    
            )
        ''')

        # Commit changes and close connection
        conn.commit()
        conn.close()

    def get_score(self, full_respones : dict):
        full_respones = str(full_respones)
        prompt = """ Evaluate the candidate's responses to the technical assessment questions below. For each answer, provide a score and brief justification.
    
                    Candidate Responses:
                    {full_respones}
    
                    Scoring Guidelines:
                    - POOR : Response shows minimal understanding, contains significant errors, or fails to address key aspects of the question
                    - GOOD : Response demonstrates solid understanding with minor gaps or imprecisions
                    - EXCELLENT : Response shows comprehensive understanding, technical accuracy, and practical application knowledge
    
                    Please evaluate each response individually, considering:
                    1. Technical accuracy of the content
                    2. Completeness of the answer (addresses all parts of the question)
                    3. Demonstration of practical knowledge and problem-solving skills
                    4. Clarity and structure of explanation
    
                    NNOTE: Do not return anything other than below output format.
                    Output Format:
                    question 1: score in percentage,
                    question 2: score in percentage,
                    question 3: score in percentage,
                    question 4: score in percentage,
                    question 5: score in percentage
        """
    
        template = PromptTemplate.from_template(prompt)
    
        # schema = {"foo": "bar"}
        # Bind schema to model
        # model_with_structure = llm.with_structured_output(schema)
        llm = ChatOpenAI(model_name="gpt-4o", api_key=self.api_key, temperature=0)
        chain = template | llm | StrOutputParser()
    
        response = chain.invoke({"full_respones":full_respones}).split(",\n")
        response =  dict([ (val.split(': ')) for val in response ])
        response =  {key: int(val.strip('%')) if '%' in val else val for key, val in response.items()}
        return response

 
    def insert_record(self, user_name, questions, answers, scores):
        # Connect to candidate.db
        conn = sqlite3.connect('candidate.db')
        cursor = conn.cursor()
    
        # Insert data into the table
        cursor.execute('''
            INSERT INTO candidates (user_name, questions, answers, scores)
            VALUES (?, ?, ?, ?)
        ''', (
            user_name,
            str(questions),  
            str(answers), 
            str(scores)    
        ))
    
        # Commit changes and close connection
        conn.commit()
        conn.close()
        print("Data inserted successfully.")

    def read_data(self, query):
        conn = sqlite3.connect('candidate.db')
        cursor = conn.cursor()
    
        # Query to get all user names
        cursor.execute(query)
        fetched_data = cursor.fetchall()
    
        conn.close()
        return fetched_data