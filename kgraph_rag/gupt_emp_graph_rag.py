import os
import warnings
from typing import List, Tuple
from dotenv import load_dotenv

# Core LangChain & Neo4j Imports
from langchain_neo4j import Neo4jGraph, Neo4jVector
from langchain_core.documents import Document
from langchain_core.messages import AIMessage, HumanMessage
from langchain_core.output_parsers import StrOutputParser
from langchain_core.prompts import ChatPromptTemplate, PromptTemplate
from langchain_core.runnables import (
    RunnableBranch,
    RunnableLambda,
    RunnableParallel,
    RunnablePassthrough,
)
from langchain.text_splitter import TokenTextSplitter

# Modern Pydantic (Fixes the warning)
from pydantic import BaseModel, Field

# Ecosystem & Model Providers
from langchain_experimental.graph_transformers import LLMGraphTransformer
from langchain_openai import ChatOpenAI, OpenAIEmbeddings
import wikipediaapi
from langchain_neo4j.vectorstores.neo4j_vector import remove_lucene_chars

# Load environment configurations
load_dotenv()

AURA_INSTANCENAME = os.environ["AURA_INSTANCENAME"]
AURA_INSTANCEID = os.environ["AURA_INSTANCEID"]
NEO4J_URI = os.environ["NEO4J_URI"]
NEO4J_USERNAME = os.environ["NEO4J_USERNAME"]
NEO4J_PASSWORD = os.environ["NEO4J_PASSWORD"]
NEO4J_DATABASE = os.environ["NEO4J_DATABASE"]
AUTH = (NEO4J_USERNAME, NEO4J_PASSWORD)


OPENAI_API_KEY = os.environ["OPENAI_API_KEY"]
OPENAI_ENDPOINT = os.environ.get("OPENAI_ENDPOINT", "https://api.openai.com/v1")

# Initialize Chat Model
chat = ChatOpenAI(api_key=OPENAI_API_KEY, temperature=0, model="gpt-4o-mini")

# Initialize Neo4j Knowledge Graph Instance
print("Connecting to Neo4j Graph Database...")
kg = Neo4jGraph(
    url=NEO4J_URI,
    username=NEO4J_USERNAME,
    password=NEO4J_PASSWORD,
    database=NEO4J_DATABASE,
)
print("Connected successfully!")

# Fetch Data Securely from Wikipedia API
# print("Fetching Wikipedia data for 'Gupta Empire'...")
# wiki_wiki = wikipediaapi.Wikipedia(
#     user_agent="MyGraphRAGApp/1.0 (your_email@example.com)", language="en"
# )

# page = wiki_wiki.page("Gupta Empire")
# raw_documents = []
# if page.exists():
#     raw_documents = Document(page_content=page.text, metadata={"source": page.fullurl})

#     # print(f"Successfully loaded document from: {page.fullurl}")
#     # print(raw_documents)
# else:
#     raise Exception("Could not find the Wikipedia page.")

# # Define chunking strategy
# text_splitter = TokenTextSplitter(chunk_size=512, chunk_overlap=24)
# documents = text_splitter.split_documents([raw_documents])
# # print(documents)

# llm_transformer = LLMGraphTransformer(llm=chat)
# graph_documents = llm_transformer.convert_to_graph_documents(documents)

# # store to Neo4j
# res = kg.add_graph_documents(graph_documents, include_source=True, baseEntityLabel=True)

# Hybrid Retrieval for RAG
# Create vector index
vector_index = Neo4jVector.from_existing_graph(
    OpenAIEmbeddings(),
    search_type="hybrid",
    node_label="Document",
    text_node_properties=["text"],
    embedding_node_property="embedding",
)

kg.query("DROP INDEX entity IF EXISTS")
kg.query(
    "CREATE FULLTEXT INDEX entity IF NOT EXISTS FOR (e:__Entity__|__entity__) ON EACH [e.id]"
)

# # Touch a dummy property on every entity node to force Neo4j to index them retroactively
# kg.query("""
# MATCH (e)
# WHERE "__Entity__" IN labels(e) OR "__entity__" IN labels(e)
# SET e.indexed_at = timestamp()
# """)

# print("Sync complete! Your full-text index is now fully populated.")


# Extract entities from text
class Entities(BaseModel):
    """Identifying information about entities."""

    names: List[str] = Field(
        ...,
        description="All the person, organization, or business entities that appear in the text.",
    )


# prompt = ChatPromptTemplate.from_messages(
#     [
#         (
#             "system",
#             "You are extracting organization and person entities from the text.",
#         ),
#         (
#             "human",
#             "Use the given format to extract information from the following. \n\ninput: {question}",
#         ),
#     ]
# )

# entity_chain = prompt | chat.with_structured_output(Entities)

# Improved, explicit entity extraction prompt
prompt = ChatPromptTemplate.from_messages(
    [
        (
            "system",
            "You are an expert entity extractor. Extract all core persons, historical empires, organizations, or concepts from the user's question. Return them as a list of strings.",
        ),
        (
            "human",
            "Question: Who was Sri Gupta?\nEntities: ['Sri Gupta']\n\nQuestion: How did the Gupta empire fall?\nEntities: ['Gupta empire']\n\nQuestion: {question}\nEntities:",
        ),
    ]
)

entity_chain = prompt | chat.with_structured_output(Entities, method="function_calling")


# Test it out:
res = entity_chain.invoke({"question": "who was Sri Gupta?"}).names
# print(res)


def generate_full_text_query(input: str) -> str:
    """
    Generate a full-text search query for a given input string.

    This function constructs a query string suitable for a full-text search.
    It processes the input string by splitting it into words and appending a
    similarity threshold (~2 changed characters) to each word, then combines
    them using the AND operator. Useful for mapping entities from user questions
    to database values, and allows for some misspelings.
    """
    full_text_query = ""
    words = [el for el in remove_lucene_chars(input).split() if el]
    for word in words[:-1]:
        full_text_query += f" {word}~2 AND"
    full_text_query += f" {words[-1]}~2"
    return full_text_query.strip()


# # Fulltext index query
# def structured_retriever(question: str) -> str:
#     """
#     Collects the neighborhood of entities mentioned
#     in the question
#     """
#     results_list = []
#     entities = entity_chain.invoke({"question": question})
#     for entity in entities.names:
#         print(f" Getting Entity: {entity}")
#         response = kg.query(
#             """CALL db.index.fulltext.queryNodes('entity', $query, {limit:2})
#             YIELD node, score
#             CALL (node) {
#               // Match outbound relationships (ignoring internal system types if desired, or all)
#               MATCH (node)-[r]->(neighbor)
#               WHERE NOT type(r) CONTAINS "MENTIONS"
#               RETURN node.id + ' - ' + type(r) + ' -> ' + neighbor.id AS output
#               UNION ALL
#               // Match inbound relationships
#               MATCH (node)<-[r]-(neighbor)
#               WHERE NOT type(r) CONTAINS "MENTIONS"
#               RETURN neighbor.id + ' - ' + type(r) + ' -> ' + node.id AS output
#             }
#             RETURN output LIMIT 50
#             """,
#             {"query": generate_full_text_query(entity)},
#         )

#         if response:
#             for row in response:
#                 if "output" in row and row["output"]:
#                     results_list.append(row["output"])

#     return "\n".join(results_list)


# print(structured_retriever("Who is Samudragupta?"))


# Fulltext index query
def structured_retriever(question: str) -> str:
    """
    Collects the neighborhood of entities mentioned
    in the question
    """
    results_list = []

    # 1. Attempt LLM extraction
    try:
        entities = entity_chain.invoke({"question": question})
        entity_names = entities.names if (entities and entities.names) else []
    except Exception as e:
        print(f" Entity extraction error: {e}")
        entity_names = []

    # 2. Fallback: If LLM returns nothing, clean the question and use it as a direct entity
    if not entity_names:
        print(" LLM extracted 0 entities. Applying fallback query cleaning...")
        # Remove common question words to isolate the core subjects
        clean_name = (
            question.replace("How did the", "")
            .replace("fall?", "")
            .replace("Who is", "")
            .replace("?", "")
        )
        entity_names = [clean_name.strip()]

    # 3. Query the Graph database
    for entity in entity_names:
        print(f" Getting Entity from Knowledge Graph: '{entity}'")
        ft_query = generate_full_text_query(entity)
        print(f" Generated Full-Text Search Query: '{ft_query}'")

        response = kg.query(
            """CALL db.index.fulltext.queryNodes('entity', $query, {limit:3})
            YIELD node, score
            CALL (node) {
              MATCH (node)-[r]->(neighbor)
              WHERE NOT type(r) CONTAINS "MENTIONS"
              RETURN node.id + ' - ' + type(r) + ' -> ' + neighbor.id AS output
              UNION ALL
              MATCH (node)<-[r]-(neighbor)
              WHERE NOT type(r) CONTAINS "MENTIONS"
              RETURN neighbor.id + ' - ' + type(r) + ' -> ' + node.id AS output
            }
            RETURN output LIMIT 50
            """,
            {"query": ft_query},
        )

        if response:
            for row in response:
                if "output" in row and row["output"]:
                    results_list.append(row["output"])

    return "\n".join(results_list)


# Final retrieval step
def retriever(question: str):
    print(f"Search query: {question}")
    structured_data = structured_retriever(question)
    unstructured_data = [
        el.page_content for el in vector_index.similarity_search(question)
    ]
    final_data = f"""
    Structured data:
    {structured_data}
    Unstructured data:
    {"#Document ".join(unstructured_data)}
    """
    print(f"\nFinal Data::: ==>{final_data}")
    return final_data


# Define the RAG chain
# Condense a chat history and follow-up question into a standlone
_template = """Given the following conversation and a follow up question, rephrase the follow up question to be a standalone question,
in its original language.
Chat History:
{chat_history}
Follow Up Input: {question}
Standalone question:"""
CONDENSE_QUESTION_PROMPT = PromptTemplate.from_template(_template)


def _format_chat_history(chat_history: List[Tuple[str, str]]) -> List:
    buffer = []
    for human, ai in chat_history:
        buffer.append(HumanMessage(content=human))
        buffer.append(AIMessage(content=ai))
    return buffer


_search_query = RunnableBranch(
    # If input includes chat_history, we condense it with the follow-up question
    (
        RunnableLambda(lambda x: bool(x.get("chat_history"))).with_config(
            run_name="HasChatHistoryCheck"
        ),  # Condense follow-up question and chat into a standalone_question
        RunnablePassthrough.assign(
            chat_history=lambda x: _format_chat_history(x["chat_history"])
        )
        | CONDENSE_QUESTION_PROMPT
        | ChatOpenAI(temperature=0)
        | StrOutputParser(),
    ),
    # Else, we have no chat history, so just pass through the question
    RunnableLambda(lambda x: x["question"]),
)

template = """Answer the question based only on the following context:
{context}

Question: {question}
Use natural language and be concise.
Answer:"""
prompt = ChatPromptTemplate.from_template(template)

chain = (
    RunnableParallel(
        {
            "context": _search_query | retriever,
            "question": RunnablePassthrough(),
        }
    )
    | prompt
    | chat
    | StrOutputParser()
)

# TEST it all out!
res_simple = chain.invoke(
    {
        "question": "How did the Gupta empire fall?",
    }
)

print(f"\n Results === {res_simple}\n\n")

# res_hist = chain.invoke(
#     {
#         "question": "When did he become the first emperor?",
#         "chat_history": [
#             ("Who was the first emperor?", "Samudragupta was the first emperor.")
#         ],
#     }
# )

# print(f"\n === {res_hist}\n\n")
