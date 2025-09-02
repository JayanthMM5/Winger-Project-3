import streamlit as st
import requests
import os
from github import Github
import base64
from datetime import datetime
from langchain.chains import LLMChain
from langchain.prompts import PromptTemplate
from langchain_community.llms import HuggingFaceHub

# Set page config
st.set_page_config(
    page_title="AI README Generator",
    page_icon="🤖",
    layout="wide",
    initial_sidebar_state="expanded"
)

# Custom CSS
st.markdown("""
<style>
    .stTextInput input {
        font-size: 18px !important;
    }
    .repo-info {
        background-color: #f0f2f6;
        border-radius: 10px;
        padding: 15px;
        margin-bottom: 20px;
    }
    .ai-response {
        background-color: #f8f9fa;
        border-left: 4px solid #4e79a7;
        padding: 10px;
        margin: 10px 0;
    }
    .stMarkdown p {
        margin-bottom: 0.5rem;
    }
</style>
""", unsafe_allow_html=True)

# Initialize Hugging Face Hub
def get_llm():
    return HuggingFaceHub(
        repo_id="mistralai/Mixtral-8x7B-Instruct-v0.1",
        huggingfacehub_api_token=st.secrets["HUGGINGFACE_API_KEY"],
        model_kwargs={"temperature": 0.7, "max_length": 4000}
    )

# Prompt templates
README_TEMPLATE = """You are an expert technical writer. Generate a comprehensive README.md file for this GitHub repository:

Repository: {repo_name}
Description: {repo_description}
Owner: {repo_owner}
Stars: {stars}
Forks: {forks}
Languages: {languages}
License: {license}

Project Structure:
{structure}

Key Files Content:
{key_files}

Additional Instructions: {additional_instructions}

Include these sections:
1. Project Title with Badges
2. Description
3. Features
4. Installation
5. Usage
6. Project Structure
7. Contributing
8. License

Make it professional and engaging. Use markdown formatting:"""

# GitHub repository analyzer
def analyze_repository(repo_url, hf_api_key):
    try:
        # Clean and validate the URL
        repo_url = repo_url.strip()
        if not repo_url.startswith(("http://", "https://")):
            repo_url = "https://" + repo_url
            
        if "github.com" not in repo_url.lower():
            raise ValueError("URL must be from GitHub")
            
        # Extract repo path (handle .git and trailing slashes)
        repo_path = (
            repo_url.split("github.com/")[1]
            .replace(".git", "")
            .strip("/")
        )
        
        # Connect to GitHub (with or without token)
        g = Github(st.secrets.get("GITHUB_TOKEN", ""))
        
        try:
            repo = g.get_repo(repo_path)
        except Exception as e:
            st.error(f"Failed to access repository: {str(e)}")
            return None
            
        # Get basic info
        metadata = {
            "name": repo.name,
            "description": repo.description or "No description available",
            "owner": repo.owner.login,
            "stars": repo.stargazers_count,
            "forks": repo.forks_count,
            "license": repo.license.name if repo.license else None,
            "url": repo.html_url
        }
        
        # Get languages with proper error handling and percentage calculation
        languages = {}
        try:
            lang_data = repo.get_languages()
            total_bytes = sum(lang_data.values())
            languages = {lang: round((bytes/total_bytes)*100, 1) for lang, bytes in lang_data.items()}
        except Exception as e:
            st.warning(f"Could not retrieve language data: {str(e)}")
        
        # Get structure (first level only)
        structure = []
        key_files_content = []
        
        try:
            contents = repo.get_contents("")
            for content in contents[:20]:  # Limit to 20 items
                if content.type == "dir":
                    structure.append(f"- {content.name}/")
                else:
                    structure.append(f"- {content.name}")
                    if content.name.endswith(('.py', '.js', '.md', '.txt')):
                        try:
                            file_content = content.decoded_content.decode('utf-8')[:1000]
                            key_files_content.append(f"File: {content.name}\n\n{file_content}\n")
                        except:
                            pass
        except Exception as content_error:
            st.warning(f"Couldn't load full structure: {str(content_error)}")
        
        return {
            "metadata": {**metadata, "languages": languages},
            "structure": "\n".join(structure),
            "key_files": "\n".join(key_files_content) if key_files_content else "No key files analyzed"
        }
        
    except Exception as e:
        st.error(f"""
        🔴 Repository Analysis Failed
        Error Type: {type(e)._name_}
        Details: {str(e)}
        
        Common Solutions:
        1. Verify the repository exists and is public
        2. Check for typos in the URL
        3. Add a GitHub token in secrets.toml
        4. Try again later if rate limited
        """)
        return None

# Generate README with AI
def generate_readme(repo_info, additional_instructions, hf_api_key):
    # Safely handle languages data
    languages_data = repo_info["metadata"].get("languages", {})
    if languages_data:
        languages_str = ", ".join([f"{k} ({v}%)" for k, v in languages_data.items()])
    else:
        languages_str = "Not available"
    
    prompt = PromptTemplate(
        template=README_TEMPLATE,
        input_variables=["repo_name", "repo_description", "repo_owner", "stars", 
                        "forks", "languages", "license", "structure", 
                        "key_files", "additional_instructions"]
    )
    
    llm = HuggingFaceHub(
        repo_id="mistralai/Mixtral-8x7B-Instruct-v0.1",
        huggingfacehub_api_token=hf_api_key,
        model_kwargs={"temperature": 0.7, "max_length": 4000}
    )
    
    chain = LLMChain(llm=llm, prompt=prompt)
    
    response = chain.run(
        repo_name=repo_info["metadata"]["name"],
        repo_description=repo_info["metadata"]["description"],
        repo_owner=repo_info["metadata"]["owner"],
        stars=repo_info["metadata"]["stars"],
        forks=repo_info["metadata"]["forks"],
        languages=languages_str,
        license=repo_info["metadata"].get("license", "None"),
        structure=repo_info["structure"],
        key_files=repo_info["key_files"],
        additional_instructions=additional_instructions
    )
    
    return response

# Download link generator
def create_download_link(content, filename):
    b64 = base64.b64encode(content.encode()).decode()
    href = f'<a href="data:file/markdown;base64,{b64}" download="{filename}">Download README.md</a>'
    return href

# Main app
def main():
    st.title("🤖 AI-Powered README Generator")
    st.markdown("Generate professional README files for GitHub repositories using AI")
    
    # Sidebar for inputs
    with st.sidebar:
        st.header("Configuration")
        hf_api_key = st.text_input("Hugging Face API Key", type="password", 
                                 help="Get your API key from huggingface.co/settings/tokens")
        
        repo_url = st.text_input("GitHub Repository URL", 
                               placeholder="https://github.com/username/repo")
        
        additional_instructions = st.text_area("Additional Instructions for AI", 
                                             placeholder="E.g., 'Focus on the machine learning aspects'")
        
        if st.button("Generate README", use_container_width=True):
            if not hf_api_key:
                st.error("Please enter your Hugging Face API key")
            elif not repo_url:
                st.error("Please enter a GitHub repository URL")
            else:
                with st.spinner("Analyzing repository..."):
                    repo_info = analyze_repository(repo_url, hf_api_key)
                    if repo_info:
                        st.session_state.repo_info = repo_info
                
                if 'repo_info' in st.session_state:
                    with st.spinner("Generating README with AI..."):
                        readme_content = generate_readme(
                            st.session_state.repo_info, 
                            additional_instructions,
                            hf_api_key
                        )
                        st.session_state.readme_content = readme_content
    
    # Main content area
    if 'repo_info' in st.session_state:
        repo_info = st.session_state.repo_info
        
        # Display repository info
        with st.expander("Repository Information", expanded=True):
            col1, col2 = st.columns(2)
            
            with col1:
                st.markdown(f"""
                <div class="repo-info">
                    <h3>{repo_info['metadata']['name']}</h3>
                    <p>{repo_info['metadata']['description'] or 'No description available'}</p>
                    <p><strong>Owner:</strong> {repo_info['metadata']['owner']}</p>
                    <p><strong>Stars:</strong> {repo_info['metadata']['stars']} | <strong>Forks:</strong> {repo_info['metadata']['forks']}</p>
                </div>
                """, unsafe_allow_html=True)
            
            with col2:
                if repo_info['metadata']['languages']:
                    st.markdown("*Languages Used:*")
                    cols = st.columns(3)
                    for i, (lang, percent) in enumerate(repo_info['metadata']['languages'].items()):
                        with cols[i % 3]:
                            st.metric(label=lang, value=f"{percent}%")
                else:
                    st.info("No language data available")
        
        # Display project structure
        with st.expander("Project Structure"):
            st.markdown(f"\n{repo_info['structure']}\n")
        
        # Display generated README
        if 'readme_content' in st.session_state:
            st.subheader("Generated README")
            
            with st.expander("Preview README", expanded=True):
                st.markdown(st.session_state.readme_content)
            
            # Download options
            st.markdown("---")
            col1, col2 = st.columns([1, 3])
            
            with col1:
                filename = st.text_input("Filename", value="README.md")
            
            with col2:
                st.markdown(create_download_link(st.session_state.readme_content, filename), 
                            unsafe_allow_html=True)
            
            st.caption(f"Generated on {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")

if __name__ == "__main__":
    # Create a secrets.toml file with your API keys
    if not os.path.exists(".streamlit/secrets.toml"):
        os.makedirs(".streamlit", exist_ok=True)
        with open(".streamlit/secrets.toml", "w") as f:
            f.write('HUGGINGFACE_API_KEY = "your-hf-key-here"\n')
            f.write('GITHUB_TOKEN = "your-gh-token-here" # optional\n')
    
    main()