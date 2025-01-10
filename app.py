# app.py
import streamlit as st
import os
from PIL import Image
from supabase import create_client, Client
import uuid
from datetime import datetime
import tempfile
from pathlib import Path

# Supabase configuration
SUPABASE_URL = st.secrets["SUPABASE_URL"]
SUPABASE_KEY = st.secrets["SUPABASE_KEY"]
supabase: Client = create_client(SUPABASE_URL, SUPABASE_KEY)

class PDFConverter:
    @staticmethod
    def convert_to_pdf(image_path: str, output_path: str):
        with Image.open(image_path) as img:
            if img.mode != 'RGB':
                img = img.convert('RGB')
            img.save(output_path, 'PDF')

def init_session_state():
    if 'user' not in st.session_state:
        st.session_state.user = None
    if 'authenticated' not in st.session_state:
        st.session_state.authenticated = False

def login_user():
    st.title("Login")
    with st.form("login_form"):
        email = st.text_input("Email")
        password = st.text_input("Password", type="password")
        submit = st.form_submit_button("Login")
        
        if submit:
            try:
                response = supabase.auth.sign_in_with_password({
                    "email": email,
                    "password": password
                })
                st.session_state.user = response.user
                st.session_state.authenticated = True
                st.success("Login successful!")
                st.rerun()
            except Exception as e:
                st.error(f"Login failed: {str(e)}")

def signup_user():
    st.title("Sign Up")
    with st.form("signup_form"):
        email = st.text_input("Email")
        password = st.text_input("Password", type="password")
        submit = st.form_submit_button("Sign Up")
        
        if submit:
            try:
                response = supabase.auth.sign_up({
                    "email": email,
                    "password": password
                })
                st.success("Signup successful! Please check your email for verification.")
            except Exception as e:
                st.error(f"Signup failed: {str(e)}")

def main_app():
    st.title("Image to PDF Converter")
    
    # File uploader
    uploaded_file = st.file_uploader(
        "Choose an image",
        type=['png', 'jpg', 'jpeg'],
        accept_multiple_files=False,
        help="Drag and drop or click to upload"
    )
    
    if uploaded_file:
        # Display image preview
        st.image(uploaded_file, caption="Preview", use_column_width=True)
        
        if st.button("Convert to PDF", type="primary"):
            with st.spinner("Converting..."):
                # Create temporary files for processing
                temp_dir = tempfile.mkdtemp()
                temp_image_path = Path(temp_dir) / "temp_image"
                temp_pdf_path = Path(temp_dir) / "output.pdf"
                
                # Save uploaded file
                with open(temp_image_path, "wb") as f:
                    f.write(uploaded_file.getbuffer())
                
                # Convert to PDF
                PDFConverter.convert_to_pdf(str(temp_image_path), str(temp_pdf_path))
                
                # Upload to Supabase Storage
                file_id = str(uuid.uuid4())
                with open(temp_pdf_path, "rb") as f:
                    supabase.storage.from_("pdfs").upload(
                        path=f"{st.session_state.user.id}/{file_id}.pdf",
                        file=f
                    )
                
                # Save conversion record to database
                supabase.table("conversions").insert({
                    "user_id": st.session_state.user.id,
                    "original_filename": uploaded_file.name,
                    "pdf_path": f"{st.session_state.user.id}/{file_id}.pdf",
                    "created_at": datetime.utcnow().isoformat()
                }).execute()
                
                # Provide download link
                with open(temp_pdf_path, "rb") as pdf_file:
                    st.download_button(
                        label="Download PDF",
                        data=pdf_file,
                        file_name="converted.pdf",
                        mime="application/pdf"
                    )
                
                # Cleanup
                os.remove(temp_image_path)
                os.remove(temp_pdf_path)
                os.rmdir(temp_dir)

def show_conversion_history():
    st.subheader("Conversion History")
    
    response = supabase.table("conversions").select("*").eq(
        "user_id", st.session_state.user.id
    ).order("created_at", desc=True).execute()
    
    for record in response.data:
        col1, col2 = st.columns([3, 1])
        with col1:
            st.write(f"Original: {record['original_filename']}")
            st.write(f"Converted: {record['created_at']}")
        with col2:
            # Generate download URL
            url = supabase.storage.from_("pdfs").get_public_url(record['pdf_path'])
            st.markdown(f"[Download]({url})")

def main():
    init_session_state()
    
    if not st.session_state.authenticated:
        tab1, tab2 = st.tabs(["Login", "Sign Up"])
        with tab1:
            login_user()
        with tab2:
            signup_user()
    else:
        main_app()
        show_conversion_history()
        
        if st.sidebar.button("Logout"):
            st.session_state.clear()
            st.rerun()

if __name__ == "__main__":
    main()