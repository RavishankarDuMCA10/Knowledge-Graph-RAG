from dotenv import load_dotenv
import os
from langchain_neo4j import Neo4jGraph
from langchain_openai import ChatOpenAI

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

chat = ChatOpenAI(api_key=OPENAI_API_KEY)

kg = Neo4jGraph(
    url=NEO4J_URI,
    username=NEO4J_USERNAME,
    password=NEO4J_PASSWORD,
    database=NEO4J_DATABASE,
)

## Example queries to interact with the Neo4j graph database
# kg.query(
#     """
#     CREATE VECTOR INDEX health_providers_embeddings IF NOT EXISTS
#     FOR (hp:HealthcareProvider) ON (hp.comprehensiveEmbedding)
#     OPTIONS {
#         indexConfig: {
#             `vector.dimensions`: 1536,
#             `vector.similarity_function`: 'cosine'
#         }
#     }
#     """
# )

# # test to see if the index was created successfully
# res = kg.query(
#     """
#     SHOW VECTOR INDEXES
#     """
# )
# print(res)


# # Create embeddings for healthcare providers and store them in the graph database
# kg.query(
#     """
#     MATCH (hp:HealthcareProvider)-[:TREATS]->(p:Patient)
#     WHERE hp.bio IS NOT NULL
#     WITH hp, genai.vector.encode(
#         hp.bio,
#         "OpenAI",
#         {
#         token: $openAiApiKey,
#         endpoint: $openAiEndpoint
#         }) AS vector
#     WITH hp, vector
#     WHERE vector IS NOT NULL
#     CALL db.create.setNodeVectorProperty(hp, "comprehensiveEmbedding", vector)
#     """,
#     params={"openAiApiKey": OPENAI_API_KEY, "openAiEndpoint": OPENAI_ENDPOINT},
# )

# ## Example query to retrieve healthcare provider nodes with their embeddings
# result = kg.query(
#     """
#     MATCH (hp:HealthcareProvider)
#     WHERE hp.bio IS NOT NULL
#     RETURN hp.bio, hp.name, hp.comprehensiveEmbedding
#     LIMIT 5
#     """
# )

# for row in result:
#     print(f"Bio: {row['hp.bio']}")
#     print(f"Name: {row['hp.name']}")
#     print("------")

# == Querying the graph for a healthcare provider
question = "give me a list of healthcare providers in the area of neuro"

# Execute the query
result = kg.query(
    """
    WITH genai.vector.encode(
        $question,
        "OpenAI",
        {
            token: $openAiApiKey,
            endpoint: $openAiEndpoint
        }
    ) AS question_embedding
    CALL db.index.vector.queryNodes(
    "health_providers_embeddings", 
    $top_k,
    question_embedding
    ) YIELD node AS healthcare_provider, score
    RETURN healthcare_provider.name, healthcare_provider.bio, score    
    """,
    params={
        "question": question,
        "top_k": 3,
        "openAiApiKey": OPENAI_API_KEY,
        "openAiEndpoint": OPENAI_ENDPOINT,
    },
)

# Print the results
for record in result:
    print(f"Provider Name: {record['healthcare_provider.name']}")
    print(f"Bio: {record['healthcare_provider.bio']}")
    print(f"Score: {record['score']}")
    print("------")
