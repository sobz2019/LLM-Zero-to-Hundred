import gradio as gr
import time
import openai
import os
from langchain.vectorstores import Chroma
from typing import List, Tuple
import re
import ast
import html
from utils.cfg import LoadConfig
APPCFG = LoadConfig()


class ChatBot:
    """
    Class representing a chatbot with document retrieval and response generation capabilities.

    This class provides static methods for responding to user queries, handling feedback, and
    cleaning references from retrieved documents.
    """
    @staticmethod
    def respond(chatbot: List, message: str, data_type: str = "Preprocessed", temperature: float = 0.0) -> Tuple:
        """
        Generate a response to a user query using document retrieval and language model completion.

        Parameters:
            chatbot (List): List representing the chatbot's conversation history.
            message (str): The user's query.
            data_type (str): Type of data used for document retrieval ("Preprocessed" or "Uploaded").
            temperature (float): Temperature parameter for language model completion.

        Returns:
            Tuple: A tuple containing an empty string, the updated chat history, and references from retrieved documents.
        """
        if data_type == "Preprocessed" or data_type == [] or data_type == None:
            # directories
            vectordb = Chroma(persist_directory=APPCFG.persist_directory,
                              embedding_function=APPCFG.embedding_model)
        elif data_type == "Uploaded":
            vectordb = Chroma(persist_directory=APPCFG.custom_persist_directory,
                              embedding_function=APPCFG.embedding_model)

        docs = vectordb.similarity_search(message, k=APPCFG.k)
        question = "# User new question:\n" + message
        references = ChatBot.clean_references(docs)
        retrieved_docs_page_content = "# Retrieved contents:\n" + \
            str(references)
        prompt = retrieved_docs_page_content + "\n\n" + question
        print("========================")
        print(prompt)
        print("========================")
        response = openai.ChatCompletion.create(
            engine=APPCFG.llm_engine,
            messages=[
                {"role": "system", "content": APPCFG.llm_system_role},
                {"role": "user", "content": prompt}
            ],
            temperature=temperature,
            # stream=False
        )
        chatbot.append(
            (message, response["choices"][0]["message"]["content"]))
        time.sleep(2)

        return "", chatbot, references

    @staticmethod
    def feedback(data: gr.LikeData):
        """
        Process user feedback on the generated response.

        Parameters:
            data (gr.LikeData): Gradio LikeData object containing user feedback.
        """
        if data.liked:
            print("You upvoted this response: " + data.value)
        else:
            print("You downvoted this response: " + data.value)

    @staticmethod
    def clean_references(documents: List) -> str:
        """
        Clean and format references from retrieved documents.

        Parameters:
            documents (List): List of retrieved documents.

        Returns:
            str: A string containing cleaned and formatted references.
        """
        server_url = "http://localhost:8000"
        documents = [str(x)+"\n\n" for x in documents]
        markdown_documents = ""
        counter = 1
        for doc in documents:
            # Extract content and metadata
            content, metadata = re.match(
                r"page_content=(.*?)( metadata=\{.*\})", doc).groups()
            metadata = metadata.split('=', 1)[1]
            metadata_dict = ast.literal_eval(metadata)

            # Decode newlines and other escape sequences
            content = bytes(content, "utf-8").decode("unicode_escape")

            # Replace escaped newlines with actual newlines
            content = re.sub(r'\\n', '\n', content)
            # Remove special tokens
            content = re.sub(r'\s*<EOS>\s*<pad>\s*', ' ', content)
            # Remove any remaining multiple spaces
            content = re.sub(r'\s+', ' ', content).strip()

            # Decode HTML entities
            content = html.unescape(content)

            # Replace incorrect unicode characters with correct ones
            content = content.encode('latin1').decode('utf-8', 'ignore')

            # Remove or replace special characters and mathematical symbols
            # This step may need to be customized based on the specific symbols in your documents
            content = re.sub(r'â', '-', content)
            content = re.sub(r'â', '∈', content)
            content = re.sub(r'Ã', '×', content)
            content = re.sub(r'ï¬', 'fi', content)
            content = re.sub(r'â', '∈', content)
            content = re.sub(r'Â·', '·', content)
            content = re.sub(r'ï¬', 'fl', content)

            pdf_url = f"{server_url}/{os.path.basename(metadata_dict['source'])}"

            # Append cleaned content to the markdown string with two newlines between documents
            markdown_documents += f"Reference {counter}:\n" + content + "\n\n" + \
                f"Filename: {os.path.basename(metadata_dict['source'])}" + " | " +\
                f"Page number: {str(metadata_dict['page'])}" + " | " +\
                f"[View PDF]({pdf_url})" "\n\n"
            counter += 1

        return markdown_documents