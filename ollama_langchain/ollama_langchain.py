import sys
import requests
from langchain_ollama import OllamaLLM
from langchain_community.utilities import SearxSearchWrapper
from langchain.agents import initialize_agent, Tool
from langchain.agents import AgentType
from langchain_core.messages import HumanMessage
from flask import Flask, request, jsonify
from flask_cors import CORS
import logging

app = Flask(__name__)
CORS(app)

# Configure logging
logging.basicConfig(level=logging.DEBUG)
logger = logging.getLogger(__name__)

# Initialize Ollama with QwQ model
llm = OllamaLLM(
    model="QwQ",
    base_url="http://host.docker.internal:11434"
)

# Print the model details to verify
logger.info(f"Using model: {llm.model}")

# Initialize SearxNG with the container name
searx_search = SearxSearchWrapper(searx_host="http://searxng:8080")

class DuckDuckGoSearchWrapper:
    def run(self, query):
        logger.debug(f"Running DuckDuckGo search for query: {query}")
        try:
            response = requests.get('https://api.duckduckgo.com/', params={
                'q': query,
                'format': 'json',
                't': 'your_app_name'  # Replace with your app name
            })
            response.raise_for_status()
            data = response.json()
            logger.debug(f"DuckDuckGo response data: {data}")
            
            # Prioritize different result types
            if data.get('AbstractText'):
                return data['AbstractText']
            elif data.get('RelatedTopics'):
                return data['RelatedTopics'][0].get('Text', 'No results found.')
            elif data.get('Definition'):
                return data['Definition']
            else:
                return 'No results found.'
        except Exception as e:
            logger.error(f"Error during DuckDuckGo search: {e}")
            return f'Error during search: {str(e)}'

# Initialize DuckDuckGo search
duckduckgo_search = DuckDuckGoSearchWrapper()

# Create a tool for web search
tools = [
    Tool(
        name="DuckDuckGo Search",
        func=duckduckgo_search.run,
        description="Useful for searching the internet for current information using DuckDuckGo."
    )
]

# Initialize the agent
agent = initialize_agent(
    tools,
    llm,
    agent=AgentType.STRUCTURED_CHAT_ZERO_SHOT_REACT_DESCRIPTION,
    verbose=True,
    handle_parsing_errors=True
)

# Add new function to get models
def get_available_models():
    try:
        logger.debug("Attempting to fetch models from Ollama...")
        response = requests.get('http://host.docker.internal:11434/api/tags')
        if response.status_code == 200:
            models = response.json()
            logger.debug(f"Successfully fetched models: {models}")
            return [model['name'] for model in models['models']]
        logger.warning(f"Failed to fetch models. Status code: {response.status_code}")
        return []
    except Exception as e:
        logger.error(f"Error fetching models: {e}")
        return []

# Add new endpoint to get models
@app.route('/models', methods=['GET'])
def models():
    logger.debug("Received request for models")
    available_models = get_available_models()
    logger.debug(f"Returning models: {available_models}")
    return jsonify({'models': available_models})

# Update query endpoint to accept model parameter
@app.route('/query', methods=['POST'])
def query():
    data = request.json
    question = data.get('question')
    model_name = data.get('model', 'QwQ')  # Default to QwQ if not specified
    
    logger.debug(f"Received query: {question} using model: {model_name}")
    
    # Create a new LLM instance with the selected model
    current_llm = OllamaLLM(
        model=model_name,
        base_url="http://host.docker.internal:11434"
    )
    
    # Create a new agent with the selected model
    current_agent = initialize_agent(
        tools,
        current_llm,
        agent=AgentType.STRUCTURED_CHAT_ZERO_SHOT_REACT_DESCRIPTION,
        verbose=True,
        handle_parsing_errors=True
    )
    
    try:
        response = current_agent.invoke([HumanMessage(content=question)])
        logger.debug(f"Agent response: {response}")
        return jsonify({'response': response['output']})
    except Exception as e:
        logger.error(f"Error during agent invocation: {str(e)}", exc_info=True)
        return jsonify({'error': str(e)}), 500

def run_without_flask():
    while True:
        query = input("Enter your question (or 'quit' to exit): ")
        if query.lower() == 'quit':
            break
        logger.debug(f"Received query: {query}")
        try:
            response = agent.invoke([HumanMessage(content=query)])
            logger.debug(f"Agent response: {response}")
            print(response['output'])
        except Exception as e:
            logger.error(f"Error during agent invocation: {str(e)}", exc_info=True)
            print(f"Error: {e}")

if __name__ == "__main__":
    if len(sys.argv) > 1 and sys.argv[1] == '--debug':
        run_without_flask()
    else:
        app.run(host='0.0.0.0', port=8081)