from langchain_google_genai import ChatGoogleGenerativeAI
import os
import re
from bs4 import BeautifulSoup

def clean_webpage_content(content):
    """
    Cleans the webpage content by removing HTML tags, scripts, symbols, and unnecessary characters.
    """
    # Parse HTML content
    soup = BeautifulSoup(content, "html.parser")
    # Remove script and style elements
    for script_or_style in soup(["script", "style"]):
        script_or_style.decompose()
    # Extract text and normalize whitespace
    text = soup.get_text(separator=" ")
    text = re.sub(r'[^\w\s]', '', text)  # Remove non-alphanumeric characters except spaces
    text = re.sub(r'\s+', ' ', text).strip()  # Normalize whitespace
    return text

def get_gemini_response(prompt, webpage_content=None):
    try:
        # Initialize the Gemini model through LangChain
        llm = ChatGoogleGenerativeAI(
            model="gemini-2.5-flash-preview-04-17",
            google_api_key=os.getenv("GOOGLE_API_KEY"),
            temperature=0.7
        )
        if webpage_content:
            webpage_content = clean_webpage_content(webpage_content)
        content_context = f"This is the webpage content:\n{webpage_content}\n" if webpage_content else ""
        complete_prompt = f"{content_context}{prompt}"
        # Get response from model
        response = llm.invoke(complete_prompt)
        return (response.content)
        
    except Exception as e:
        return f"Error: {str(e)}"