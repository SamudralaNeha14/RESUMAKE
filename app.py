import json
import os
import traceback
from io import BytesIO

import streamlit as st
from langchain_core.prompts import ChatPromptTemplate
from langchain_groq import ChatGroq

# Import for file handling
try:
    import PyPDF2
    PDF_SUPPORT = True
except ImportError:
    PDF_SUPPORT = False

try:
    from docx import Document
    from docx.enum.text import WD_ALIGN_PARAGRAPH
    from docx.shared import Pt
    DOCX_SUPPORT = True
except ImportError:
    DOCX_SUPPORT = False

try:
    from reportlab.lib.enums import TA_CENTER, TA_LEFT
    from reportlab.lib.pagesizes import letter
    from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
    from reportlab.lib.units import inch
    from reportlab.platypus import Paragraph, SimpleDocTemplate, Spacer
    PDF_EXPORT_SUPPORT = True
except ImportError:
    PDF_EXPORT_SUPPORT = False

# Page configuration
st.set_page_config(
    page_title="AI Resume Builder & ATS Scanner",
    page_icon="📄",
    layout="wide",
    initial_sidebar_state="expanded"
)

# Initialize Groq LLM
@st.cache_resource
def init_llm(api_key):
    if not api_key:
        return None
    return ChatGroq(
        temperature=0.3,
        model_name="llama-3.3-70b-versatile",
        groq_api_key=api_key
    )

# Get API key from environment or secrets
def get_api_key():
    api_key = os.getenv("GROQ_API_KEY")
    if api_key:
        return api_key
    try:
        return st.secrets["GROQ_API_KEY"]
    except (FileNotFoundError, KeyError):
        pass
    return ""

# Initialize with existing API key
initial_api_key = get_api_key()
llm = init_llm(initial_api_key) if initial_api_key else None

# Initialize session state
if 'resume_data' not in st.session_state:
    st.session_state.resume_data = {
        'personal_info': {},
        'education': [],
        'certifications': [],
        'experience': [],
        'projects': [],
        'skills': []
    }
if 'generated_resume' not in st.session_state:
    st.session_state.generated_resume = ""
if 'ats_score' not in st.session_state:
    st.session_state.ats_score = None
if 'ats_feedback' not in st.session_state:
    st.session_state.ats_feedback = ""
if 'edit_mode' not in st.session_state:
    st.session_state.edit_mode = False
if 'page' not in st.session_state:
    st.session_state.page = "Home"
if 'chat_history' not in st.session_state:
    st.session_state.chat_history = []
if 'uploaded_resume' not in st.session_state:
    st.session_state.uploaded_resume = ""

# FIXED: Function to generate PDF with proper error handling
def create_pdf(resume_text):
    """Generate PDF from resume text and return bytes object"""
    try:
        if not PDF_EXPORT_SUPPORT:
            st.error("❌ PDF library not installed. Run: pip install reportlab")
            return None
        
        if not resume_text or not resume_text.strip():
            st.error("❌ Resume text is empty")
            return None
        
        buffer = BytesIO()
        doc = SimpleDocTemplate(
            buffer, 
            pagesize=letter,
            topMargin=0.5*inch,
            bottomMargin=0.5*inch,
            leftMargin=0.5*inch,
            rightMargin=0.5*inch
        )
        
        styles = getSampleStyleSheet()
        story = []
        
        lines = resume_text.split('\n')
        for i, line in enumerate(lines):
            line = line.strip()
            if not line:
                story.append(Spacer(1, 0.05*inch))
                continue
            
            # Escape HTML special characters
            line = line.replace('&', '&amp;').replace('<', '&lt;').replace('>', '&gt;')
            
            # Simple style detection
            if i == 0:
                p = Paragraph(f"<b><font size=14>{line}</font></b>", styles['Normal'])
            elif line.isupper() and len(line.split()) <= 8:
                p = Paragraph(f"<b><font size=12>{line}</font></b>", styles['Normal'])
            else:
                p = Paragraph(line, styles['Normal'])
            
            story.append(p)
        
        doc.build(story)
        buffer.seek(0)
        pdf_bytes = buffer.getvalue()
        
        if not pdf_bytes:
            st.error("❌ PDF generation produced empty output")
            return None
        
        return pdf_bytes
        
    except Exception as e:
        st.error(f"❌ PDF Export Error: {str(e)}")
        print(f"PDF Error: {traceback.format_exc()}")
        return None

# FIXED: Function to generate DOCX with proper error handling
def create_docx(resume_text):
    """Generate DOCX from resume text and return bytes object"""
    try:
        if not DOCX_SUPPORT:
            st.error("❌ DOCX library not installed. Run: pip install python-docx")
            return None
        
        if not resume_text or not resume_text.strip():
            st.error("❌ Resume text is empty")
            return None
        
        doc = Document()
        
        lines = resume_text.split('\n')
        for i, line in enumerate(lines):
            line = line.strip()
            if not line:
                doc.add_paragraph()
                continue
            
            p = doc.add_paragraph(line)
            
            # Style the text
            for run in p.runs:
                run.font.size = Pt(11)
            
            if i == 0:
                p.alignment = WD_ALIGN_PARAGRAPH.CENTER
                for run in p.runs:
                    run.font.size = Pt(14)
                    run.font.bold = True
            elif line.isupper() and len(line.split()) <= 8:
                for run in p.runs:
                    run.font.size = Pt(12)
                    run.font.bold = True
        
        buffer = BytesIO()
        doc.save(buffer)
        buffer.seek(0)
        docx_bytes = buffer.getvalue()
        
        if not docx_bytes:
            st.error("❌ DOCX generation produced empty output")
            return None
        
        return docx_bytes
        
    except Exception as e:
        st.error(f"❌ DOCX Export Error: {str(e)}")
        print(f"DOCX Error: {traceback.format_exc()}")
        return None

# Sidebar navigation
with st.sidebar:
    st.title("🤖 AI Resume Builder")
    
    has_api_key = bool(initial_api_key)
    
    if has_api_key:
        st.success("✅ API Key Configured")
    else:
        st.warning("⚠️ API Key Required")
        with st.expander("Configure API Key"):
            groq_api_key = st.text_input(
                "Enter Groq API Key", 
                type="password",
                help="Get one at https://console.groq.com"
            )
            if groq_api_key:
                os.environ["GROQ_API_KEY"] = groq_api_key
                llm = init_llm(groq_api_key)
                st.success("✅ API Key saved!")
                st.rerun()
    
    st.markdown("---")
    
    st.markdown("### 📂 Select Option")
    
    if st.button("🏠 Home", use_container_width=True, type="primary" if st.session_state.page == "Home" else "secondary"):
        st.session_state.page = "Home"
        st.rerun()
    
    if st.button("📝 Resume Builder", use_container_width=True, type="primary" if st.session_state.page == "Resume Builder" else "secondary"):
        st.session_state.page = "Resume Builder"
        st.rerun()
    
    if st.button("🔍 ATS Scanner", use_container_width=True, type="primary" if st.session_state.page == "ATS Scanner" else "secondary"):
        st.session_state.page = "ATS Scanner"
        st.rerun()
    
    if st.button("💬 AI Assistant", use_container_width=True, type="primary" if st.session_state.page == "AI Assistant" else "secondary"):
        st.session_state.page = "AI Assistant"
        st.rerun()
    
    st.markdown("---")
    st.markdown("### 📁 File Support")
    st.markdown(f"- TXT: ✅")
    st.markdown(f"- PDF: {'✅' if PDF_SUPPORT else '❌ (pip install PyPDF2)'}")
    st.markdown(f"- DOCX: {'✅' if DOCX_SUPPORT else '❌ (pip install python-docx)'}")
    st.markdown(f"- PDF Export: {'✅' if PDF_EXPORT_SUPPORT else '❌ (pip install reportlab)'}")
    
    st.markdown("---")
    st.caption("Made with ❤️ using Groq Cloud + LangChain")

# Main content based on selected page
if st.session_state.page == "Home":
    st.markdown("<h1 style='text-align: center; color: #1f77b4; font-size: 3.5em;'>🤖 AI RESUME BUILDER & ATS SCANNER</h1>", unsafe_allow_html=True)
    st.markdown("<p style='text-align: center; font-size: 1.3em; color: #666;'>Build professional resumes and optimize them for Applicant Tracking Systems</p>", unsafe_allow_html=True)
    st.markdown("<br>", unsafe_allow_html=True)
    
    col1, col2 = st.columns(2)
    
    with col1:
        st.markdown("""
        <div style='padding: 30px; background: linear-gradient(135deg, #667eea 0%, #764ba2 100%); border-radius: 15px; color: white; box-shadow: 0 4px 6px rgba(0,0,0,0.1);'>
            <h2 style='color: white; margin-top: 0;'>📝 Resume Builder</h2>
            <p style='font-size: 1.1em; line-height: 1.6;'>Create professional, ATS-optimized resumes with AI assistance.</p>
        </div>
        """, unsafe_allow_html=True)
    
    with col2:
        st.markdown("""
        <div style='padding: 30px; background: linear-gradient(135deg, #f093fb 0%, #f5576c 100%); border-radius: 15px; color: white; box-shadow: 0 4px 6px rgba(0,0,0,0.1);'>
            <h2 style='color: white; margin-top: 0;'>🔍 ATS Scanner</h2>
            <p style='font-size: 1.1em; line-height: 1.6;'>Analyze your resume against job descriptions.</p>
        </div>
        """, unsafe_allow_html=True)

elif st.session_state.page == "Resume Builder":
    st.title("📝 Resume Builder")
    st.markdown("Build your professional ATS-optimized resume")
    
    with st.expander("👤 Personal Information", expanded=True):
        col1, col2 = st.columns(2)
        with col1:
            name = st.text_input("Full Name*", key="name_input")
            email = st.text_input("Email*", key="email_input")
            phone = st.text_input("Phone", key="phone_input")
        with col2:
            linkedin = st.text_input("LinkedIn URL", key="linkedin_input")
            github = st.text_input("GitHub URL", key="github_input")
            portfolio = st.text_input("Portfolio URL", key="portfolio_input")
        
        target_role = st.text_input("Target Role*", placeholder="e.g., Software Engineer | Data Scientist", key="target_input")
        summary = st.text_area("Professional Summary", placeholder="Brief overview of your experience and goals", key="summary_input")
        
        if st.button("Save Personal Info", key="save_personal"):
            st.session_state.resume_data['personal_info'] = {
                'name': name, 'email': email, 'phone': phone,
                'linkedin': linkedin, 'github': github, 'portfolio': portfolio,
                'target_role': target_role, 'summary': summary
            }
            st.success("✅ Personal information saved!")
    
    with st.expander("🎓 Education"):
        num_edu = st.number_input("Number of Education Entries", min_value=0, max_value=10, value=1, key="num_edu")
        education_entries = []
        
        for i in range(num_edu):
            st.markdown(f"**Education #{i+1}**")
            col1, col2 = st.columns(2)
            with col1:
                degree = st.text_input(f"Degree", key=f"edu_degree_{i}")
                institution = st.text_input(f"Institution", key=f"edu_inst_{i}")
            with col2:
                year = st.text_input(f"Year", key=f"edu_year_{i}")
                gpa = st.text_input(f"GPA (optional)", key=f"edu_gpa_{i}")
            
            if degree and institution:
                education_entries.append({
                    'degree': degree, 'institution': institution,
                    'year': year, 'gpa': gpa
                })
            st.markdown("---")
        
        if st.button("Save Education", key="save_edu"):
            st.session_state.resume_data['education'] = education_entries
            st.success("✅ Education saved!")
    
    with st.expander("💼 Work Experience"):
        num_exp = st.number_input("Number of Work Experiences", min_value=0, max_value=10, value=1, key="num_exp")
        exp_entries = []
        
        for i in range(num_exp):
            st.markdown(f"**Experience #{i+1}**")
            col1, col2 = st.columns(2)
            with col1:
                title = st.text_input(f"Job Title", key=f"exp_title_{i}")
                company = st.text_input(f"Company", key=f"exp_company_{i}")
            with col2:
                duration = st.text_input(f"Duration", key=f"exp_duration_{i}", 
                                        placeholder="e.g., January 2022 - Present")
            
            description = st.text_area(f"Key Achievements & Responsibilities (one per line)", 
                                      key=f"exp_desc_{i}", height=150)
            
            if title and company:
                exp_entries.append({
                    'title': title, 'company': company,
                    'duration': duration, 'description': description
                })
            st.markdown("---")
        
        if st.button("Save Work Experience", key="save_exp"):
            st.session_state.resume_data['experience'] = exp_entries
            st.success("✅ Work experience saved!")
    
    with st.expander("🛠️ Skills"):
        num_skills = st.number_input("Number of Skill Categories", min_value=0, max_value=10, value=1, key="num_skills")
        skill_entries = []
        
        for i in range(num_skills):
            st.markdown(f"**Skill Category #{i+1}**")
            col1, col2 = st.columns(2)
            with col1:
                category = st.text_input(f"Category", key=f"skill_cat_{i}",
                                        placeholder="e.g., Programming Languages")
            with col2:
                items = st.text_input(f"Skills (comma separated)", key=f"skill_items_{i}",
                                     placeholder="e.g., Python, Java, JavaScript")
            
            if category and items:
                skill_entries.append({
                    'category': category, 'items': items
                })
            st.markdown("---")
        
        if st.button("Save Skills", key="save_skills"):
            st.session_state.resume_data['skills'] = skill_entries
            st.success("✅ Skills saved!")
    
    st.markdown("---")
    if st.button("🚀 Generate Resume", type="primary", use_container_width=True, key="generate_btn"):
        if not initial_api_key or not llm:
            st.error("⚠️ Please configure your Groq API key in the sidebar first!")
        elif not st.session_state.resume_data['personal_info'].get('name'):
            st.error("Please fill in at least the personal information section!")
        else:
            with st.spinner("Generating your ATS-optimized resume..."):
                resume_prompt = ChatPromptTemplate.from_messages([
                    ("system", """You are an expert resume writer. Create a professional, ATS-optimized resume in plain text format.
                    
Use this structure:
- NAME at top
- Contact info
- PROFESSIONAL SUMMARY
- WORK EXPERIENCE with bullet points
- EDUCATION
- SKILLS
- Use strong action verbs and metrics"""),
                    ("human", """Create a professional resume with this information:

Personal: {personal_info}
Education: {education}
Experience: {experience}
Skills: {skills}

Generate in clean text format.""")
                ])
                
                resume_data = st.session_state.resume_data
                chain = resume_prompt | llm
                response = chain.invoke({
                    "personal_info": json.dumps(resume_data['personal_info'], indent=2),
                    "education": json.dumps(resume_data['education'], indent=2),
                    "experience": json.dumps(resume_data['experience'], indent=2),
                    "skills": json.dumps(resume_data['skills'], indent=2),
                })
                
                st.session_state.generated_resume = response.content
                st.session_state.edit_mode = False
                st.success("✅ Resume generated successfully!")
                st.rerun()
    
    if st.session_state.generated_resume:
        st.markdown("---")
        st.subheader("📄 Generated Resume")
        
        col1, col2 = st.columns([1, 3])
        with col1:
            if st.button("✏️ Edit" if not st.session_state.edit_mode else "👁️ View", use_container_width=True):
                st.session_state.edit_mode = not st.session_state.edit_mode
                st.rerun()
        
        if st.session_state.edit_mode:
            edited_resume = st.text_area(
                "Edit Your Resume",
                value=st.session_state.generated_resume,
                height=600,
                key="edit_resume_area"
            )
            if st.button("💾 Save Changes", use_container_width=True):
                st.session_state.generated_resume = edited_resume
                st.session_state.edit_mode = False
                st.success("✅ Changes saved!")
                st.rerun()
        else:
            st.text_area(
                "Resume Preview",
                value=st.session_state.generated_resume,
                height=600,
                disabled=True,
                key="view_resume_area"
            )
        
        st.markdown("### 💾 Download Resume")
        
        file_name_base = st.session_state.resume_data['personal_info'].get('name', 'resume').replace(' ', '_')
        
        col1, col2, col3 = st.columns(3)
        
        with col1:
            st.download_button(
                label="📥 Download TXT",
                data=st.session_state.generated_resume,
                file_name=f"{file_name_base}_resume.txt",
                mime="text/plain",
                use_container_width=True,
                key="dl_txt"
            )
        
        with col2:
            pdf_buffer = create_pdf(st.session_state.generated_resume)
            if pdf_buffer:
                st.download_button(
                    label="📥 Download PDF",
                    data=pdf_buffer,
                    file_name=f"{file_name_base}_resume.pdf",
                    mime="application/pdf",
                    use_container_width=True,
                    key="dl_pdf"
                )
        
        with col3:
            docx_buffer = create_docx(st.session_state.generated_resume)
            if docx_buffer:
                st.download_button(
                    label="📥 Download DOCX",
                    data=docx_buffer,
                    file_name=f"{file_name_base}_resume.docx",
                    mime="application/vnd.openxmlformats-officedocument.wordprocessingml.document",
                    use_container_width=True,
                    key="dl_docx"
                )

elif st.session_state.page == "ATS Scanner":
    st.title("🔍 ATS Resume Scanner")
    st.markdown("Analyze your resume against job descriptions")
    
    if not initial_api_key or not llm:
        st.error("⚠️ Please configure your Groq API key in the sidebar first!")
    else:
        resume_source = st.radio(
            "Choose Resume Source:",
            ["Use Generated Resume", "Upload Resume File", "Paste Resume Text"],
            horizontal=True
        )
        
        resume_to_scan = ""
        
        if resume_source == "Use Generated Resume":
            if not st.session_state.generated_resume:
                st.warning("⚠️ No generated resume found. Please generate a resume in the Resume Builder first.")
            else:
                resume_to_scan = st.session_state.generated_resume
                st.success("✅ Using generated resume")
        
        elif resume_source == "Upload Resume File":
            uploaded_file = st.file_uploader(
                "Upload your resume",
                type=['txt', 'pdf', 'docx'],
                help="Upload your existing resume"
            )
            
            if uploaded_file is not None:
                try:
                    if uploaded_file.type == "text/plain":
                        resume_to_scan = uploaded_file.read().decode("utf-8")
                        st.session_state.uploaded_resume = resume_to_scan
                        st.success(f"✅ Resume uploaded: {uploaded_file.name}")
                    
                    elif uploaded_file.type == "application/pdf" and PDF_SUPPORT:
                        pdf_reader = PyPDF2.PdfReader(uploaded_file)
                        resume_to_scan = ""
                        for page in pdf_reader.pages:
                            text = page.extract_text()
                            if text:
                                resume_to_scan += text + "\n"
                        st.session_state.uploaded_resume = resume_to_scan
                        st.success(f"✅ PDF uploaded: {uploaded_file.name}")
                    
                    elif uploaded_file.type == "application/vnd.openxmlformats-officedocument.wordprocessingml.document" and DOCX_SUPPORT:
                        doc = Document(uploaded_file)
                        resume_to_scan = "\n".join([para.text for para in doc.paragraphs if para.text.strip()])
                        st.session_state.uploaded_resume = resume_to_scan
                        st.success(f"✅ DOCX uploaded: {uploaded_file.name}")
                
                except Exception as e:
                    st.error(f"❌ Error reading file: {str(e)}")
        
        else:
            pasted_resume = st.text_area(
                "Paste Your Resume Text",
                placeholder="Paste your resume content here...",
                height=300,
                key="paste_resume"
            )
            
            if pasted_resume:
                resume_to_scan = pasted_resume
                st.session_state.uploaded_resume = pasted_resume
        
        st.markdown("---")
        job_description = st.text_area(
            "📋 Job Description*",
            placeholder="Paste the job description here...",
            height=300,
            key="job_desc"
        )
        
        if st.button("🔍 Scan Resume", type="primary", use_container_width=True):
            if not resume_to_scan:
                st.error("Please provide a resume!")
            elif not job_description:
                st.error("Please provide a job description!")
            else:
                with st.spinner("Analyzing your resume..."):
                    ats_prompt = ChatPromptTemplate.from_messages([
                        ("system", "You are an ATS analyzer. Provide a score 0-100 and detailed feedback."),
                        ("human", """Analyze this resume for ATS compatibility against the job description.

Job Description:
{job_description}

Resume:
{resume}

Provide score and feedback.""")
                    ])
                    
                    chain = ats_prompt | llm
                    response = chain.invoke({
                        "job_description": job_description,
                        "resume": resume_to_scan
                    })
                    
                    st.session_state.ats_feedback = response.content
                    st.session_state.ats_score = 75
        
        if st.session_state.ats_feedback:
            st.markdown("---")
            st.markdown("### 📊 Analysis Results")
            st.info(st.session_state.ats_feedback)

elif st.session_state.page == "AI Assistant":
    st.title("💬 AI Assistant")
    st.markdown("Get AI-powered assistance for your resume")
    
    if not initial_api_key or not llm:
        st.error("⚠️ Please configure your Groq API key in the sidebar first!")
    else:
        st.markdown("### 💬 Chat with AI Assistant")
        
        for message in st.session_state.chat_history:
            if isinstance(message, dict) and "role" in message:
                if message["role"] == "user":
                    st.markdown(f"**You:** {message['content']}")
                else:
                    st.markdown(f"**Assistant:** {message['content']}")
        
        user_input = st.text_input(
            "Ask for assistance (e.g., 'Improve my work experience', 'Add more action verbs')",
            placeholder="Type your question or request...",
            key="ai_input"
        )
        
        if user_input:
            with st.spinner("Getting AI assistance..."):
                st.session_state.chat_history.append({
                    "role": "user",
                    "content": user_input
                })
                
                assist_prompt = ChatPromptTemplate.from_messages([
                    ("system", "You are an expert resume consultant. Provide specific, actionable resume improvement suggestions."),
                    ("human", "Request: {user_input}\n\nProvide helpful advice for resume improvement.")
                ])
                
                chain = assist_prompt | llm
                response = chain.invoke({
                    "user_input": user_input
                })
                
                st.session_state.chat_history.append({
                    "role": "assistant",
                    "content": response.content
                })
                
                st.rerun()
        
        if st.session_state.chat_history:
            if st.button("🗑️ Clear Chat History", use_container_width=True):
                st.session_state.chat_history = []
                st.rerun()
