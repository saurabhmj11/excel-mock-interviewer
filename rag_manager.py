import os
import json
from typing import List, Dict
from chromadb import Documents, Embeddings, IDs
import chromadb
from openai import OpenAI
from openai import embeddings
import tiktoken # For token counting (optional, but good for chunking strategy)

from interview_agent import Question # Import our Question data model


class RAGManager:
    def __init__(self, questions: List[Question], collection_name: str = "excel_interview_qa"):
        self.questions = questions
        self.collection_name = collection_name

        # Initialize OpenAI client for embeddings
        self.openai_client = OpenAI()
        if not os.getenv("OPENAI_API_KEY"):
            raise ValueError("OPENAI_API_KEY environment variable not set. Cannot initialize OpenAI embeddings.")

        # Initialize ChromaDB client. For simplicity, we'll use a persistent client in a local directory.
        # In a production environment, you might use a client-server setup.
        self.chroma_client = chromadb.PersistentClient(path="./chroma_db") # Stores data locally in this folder

        try:
            self.collection = self.chroma_client.get_or_create_collection(name=self.collection_name)
            if self.collection.count() == 0: # Only build if collection is empty
                print(f"ChromaDB collection '{self.collection_name}' is empty. Building knowledge base...")
                self._build_knowledge_base()
            else:
                print(f"ChromaDB collection '{self.collection_name}' already exists with {self.collection.count()} documents. Skipping build.")
        except Exception as e:
            print(f"An error occurred with ChromaDB or OpenAI: {e}")
            raise # Re-raise to stop if RAG cannot be initialized


    def _get_embedding(self, text: str) -> List[float]:
        """Generates an embedding for the given text using OpenAI's embedding model."""
        # Note: text-embedding-ada-002 is recommended by OpenAI for general purpose embeddings
        # Newer models like text-embedding-3-small or large can also be used.
        response = self.openai_client.embeddings.create(
            input=text,
            model="text-embedding-ada-002" 
        )
        return response.data[0].embedding

    def _build_knowledge_base(self):
        """
        Builds the knowledge base by embedding each question's ideal answer
        and adding it to the ChromaDB collection.
        Each document will contain the ideal answer text.
        Metadata will include question ID, text, difficulty, and topic to make retrieval more precise if needed.
        """
        documents: Documents = []
        metadatas: List[Dict] = []
        ids: IDs = []

        for q in self.questions:
            # We'll embed the ideal_answer and store it. The question text in metadata helps for context.
            documents.append(q.ideal_answer)
            metadatas.append({
                "question_id": q.id,
                "question_text": q.text, # Original question helps ground context.
                "difficulty": q.difficulty,
                "topic": q.topic
            })
            ids.append(q.id) # Use question ID as the document ID

        if documents:
            # Add to ChromaDB. ChromaDB will handle embedding if not provided directly,
            # but using OpenAI's client gives us more control and uses their recommended model.
            # We will generate embeddings explicitly and pass them.
            embeddings_list = []
            for doc_text in documents:
                embeddings_list.append(self._get_embedding(doc_text))
            
            self.collection.add(
                documents=documents,
                metadatas=metadatas,
                embeddings=embeddings_list, # Provide explicit embeddings
                ids=ids
            )
            print(f"Successfully added {len(documents)} documents to ChromaDB collection '{self.collection_name}'.")
        else:
            print("No documents to add to the knowledge base.")

    def retrieve_context(self, query: str, n_results: int = 1) -> List[Dict]:
        """
        Retrieves the most relevant context (ideal answers) from the knowledge base
        based on the query (user's question).
        """
        if not query:
            return []

        try:
            # Query the ChromaDB collection
            results = self.collection.query(
                query_embeddings=[self._get_embedding(query)], # Embed the query
                n_results=n_results,                            # Number of similar results to retrieve
                include=['documents', 'metadatas']              # Include content and metadata
            )
            
            # Format results for easier consumption
            context = []
            if results and results['documents']:
                for i in range(len(results['documents'][0])):
                    context.append({
                        "document": results['documents'][0][i],
                        "metadata": results['metadatas'][0][i],
                        "distance": results['distances'][0][i] if results['distances'] else None
                    })
            return context
        except Exception as e:
            print(f"Error during context retrieval from ChromaDB: {e}")
            return []

# Example usage (can be run standalone for testing RAGManager)
if __name__ == "__main__":
    # Create some dummy questions for testing (in a real app, load from questions.json)
    dummy_questions = [
        Question("q_sum", "What is SUM function?", "easy", "Formulas", "The SUM function adds numbers in a range. `=SUM(A1:A10)`."),
        Question("q_vlookup", "Explain VLOOKUP.", "medium", "Lookup", "VLOOKUP finds values in a table. `=VLOOKUP(lookup_value, table_array, col_index_num, [range_lookup])`.")
    ]

    print("Initializing RAGManager...")
    try:
        rag_manager = RAGManager(questions=dummy_questions)
        
        test_query = "How do I find data in a large table?"
        print(f"\nRetrieving context for query: '{test_query}'")
        retrieved_context = rag_manager.retrieve_context(test_query)
        
        if retrieved_context:
            for item in retrieved_context:
                print(f"  Retrieved Document (Q ID: {item['metadata']['question_id']}, Distance: {item['distance']}):")
                print(f"    '{item['document'][:100]}...'")
        else:
            print("No context retrieved.")

        test_query_2 = "Adding numbers in excel"
        print(f"\nRetrieving context for query: '{test_query_2}'")
        retrieved_context_2 = rag_manager.retrieve_context(test_query_2)
        if retrieved_context_2:
            for item in retrieved_context_2:
                print(f"  Retrieved Document (Q ID: {item['metadata']['question_id']}, Distance: {item['distance']}):")
                print(f"    '{item['document'][:100]}...'")
        else:
            print("No context retrieved.")

    except ValueError as e:
        print(f"Error: {e}")
        print("Please ensure OPENAI_API_KEY is set in your environment variables.")
